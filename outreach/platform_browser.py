"""Opt-in VPS-owned persistent browser. Normal UI navigation, never developer APIs."""
import asyncio
import hashlib
import re
import time
from pathlib import Path
from urllib.parse import urlsplit, urlencode, parse_qs

from .browser import browser_environment
from .web import domain_of, crawl_url, normalize_email, EMAIL_RE
from .platform_access import hold, record_hold, response_issue

ASSET_HOSTS = {'linkedin.com','licdn.com','x.com','twitter.com','twimg.com'}


class LoginTransitionError(Exception):
    """Navigation reached a login/challenge route; its document is not evidence."""


def login_transition(target, current):
    """Recognize only an actual same-platform authentication redirect."""
    try:
        expected, observed = urlsplit(target), urlsplit(current)
        host = (observed.hostname or '').lower()
        if observed.scheme != 'https' or observed.username or observed.password or observed.port:
            return False
        expected_host = (expected.hostname or '').lower()
        if expected_host == 'linkedin.com' or expected_host.endswith('.linkedin.com'):
            return (host == 'linkedin.com' or host.endswith('.linkedin.com')) and bool(
                re.match(r'^/(?:login|authwall|checkpoint)(?:/|$)', observed.path))
        if expected.hostname in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}:
            return host in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'} and bool(
                re.match(r'^/i/flow/login(?:/|$)', observed.path))
    except ValueError:
        pass
    return False


def profile_target(url):
    from .profiles import canonical_profile
    value=canonical_profile(url)
    parts=urlsplit(value)
    host=domain_of(value)
    if host=='linkedin.com' or host.endswith('.linkedin.com'):
        if not parts.path.startswith('/company/'):
            raise ValueError('Use the professional-profile reader for personal LinkedIn business candidates')
        return 'linkedin.com', 'https://www.linkedin.com'+parts.path.rstrip('/')+'/about/'
    if host in {'x.com','twitter.com'}:
        return 'x.com', 'https://x.com'+parts.path.rstrip('/')
    raise ValueError('Managed browser supports company LinkedIn About and X public profile routes only')


def search_target(platform,query):
    if not 5<=len(query)<=500:
        raise ValueError('Use a bounded business query')
    if platform=='linkedin.com':
        return 'https://www.linkedin.com/search/results/companies/?'+urlencode({'keywords':query})
    if platform=='x.com':
        return 'https://x.com/search?'+urlencode({'q':query,'f':'user'})
    raise ValueError('Unsupported platform search')


class BrowserSession:
    def __init__(self,settings):
        self.settings=settings
        self.context=self.playwright=self.file_lock=None
        self.last_access_issue={}

    async def __aenter__(self):
        from .worker import WorkerLock
        from playwright.async_api import async_playwright
        profile=self.settings.data_dir/'platform-browser'
        profile.mkdir(parents=True,exist_ok=True,mode=0o700)
        try:
            self.file_lock=WorkerLock(profile/'session.lock')
            self.playwright=await async_playwright().start()
            self.context=await self.playwright.chromium.launch_persistent_context(str(profile/'profile'),
                headless=self.settings.platform_browser_headless,chromium_sandbox=True,
                viewport={'width':1440,'height':900},accept_downloads=False,service_workers='block',
                env=browser_environment(),timeout=self.settings.platform_browser_timeout_seconds*1000)
            await self.context.route('**/*',self.route)
            await self.context.route_web_socket('**/*',lambda socket:socket.close())
            return self
        except BaseException:
            await self.__aexit__(None,None,None)
            raise

    async def route(self,route):
        try:
            parts=urlsplit(route.request.url)
            host=(parts.hostname or '').lower()
            invalid=parts.scheme not in {'https','http'} or parts.username or parts.password or parts.port
        except ValueError:
            invalid=True
        if invalid:
            await route.abort()
            return
        if not any(host==d or host.endswith('.'+d) for d in ASSET_HOSTS):
            await route.abort()
            return
        if route.request.is_navigation_request() and route.request.frame==route.request.frame.page.main_frame:
            path=parts.path
            allowed=((host=='linkedin.com' or host.endswith('.linkedin.com')) and (re.fullmatch(r'/company/[A-Za-z0-9_-]+(?:/about|/posts)?/?',path) or re.fullmatch(r'/in/[A-Za-z0-9_-]{2,100}(?:/details/experience|/overlay/contact-info)?/?',path) or re.fullmatch(r'/search/results/(?:companies|people)/?',path) or re.match(r'^/(?:login|authwall|checkpoint)(?:/|$)',path))
                     or host in {'x.com','www.x.com','twitter.com','www.twitter.com'} and (path=='/search' or path.startswith('/i/flow/login') or re.fullmatch(r'/[A-Za-z0-9_]{1,15}/?',path) and path.strip('/').lower() not in {'messages','notifications','settings','compose','home','i'}))
            if not allowed:
                await route.abort()
                return
        await route.continue_()

    async def navigate(self,url):
        page=await self.context.new_page()
        timeout=self.settings.platform_browser_timeout_seconds
        observed_status=None
        observed_response=None
        def observe(response):
            nonlocal observed_status, observed_response
            if response.request.is_navigation_request() and response.frame==page.main_frame:
                observed_status=response.status
                observed_response=response
        page.on('response',observe)
        try:
            response=await page.goto(url,wait_until='domcontentloaded',timeout=timeout*1000)
        except Exception:
            # Chromium may reject a custom denial status before goto returns.
            # Preserve the actual main-document response instead of reporting
            # an opaque browser error or trying to read its error document.
            if observed_status and observed_status>=400:
                self.last_access_issue=await response_issue(observed_response)
                return page,observed_status
            if login_transition(url, page.url):
                raise LoginTransitionError() from None
            raise
        finally:
            page.remove_listener('response',observe)
        if response and response.status>=400:
            self.last_access_issue=await response_issue(response)
            return page,response.status
        return page, None

    async def __aexit__(self,*args):
        try:
            if self.context:
                await self.context.close()
        finally:
            try:
                if self.playwright:
                    await self.playwright.stop()
            finally:
                if self.file_lock:
                    self.file_lock.close()


async def browser_snapshot(settings,url):
    platform,target=profile_target(url)
    base={'url':target,'capture_method':'managed_browser_public_profile','scope':'visible_business_fields',
          'profile_snapshot':True,'observed_at':time.time(),'identity_verified':False}
    if blocked:=hold(settings,platform):
        return {**base,**blocked,'state':'operator_attention'}
    try:
        async with settings._platform_browser_lock:
            if blocked:=hold(settings,platform):
                return {**base,**blocked,'state':'operator_attention'}
            return await _snapshot_locked(settings,platform,target,base)
    except LoginTransitionError:
        blocked=record_hold(settings,platform,'login_or_challenge')
        return {**base,**blocked,'state':'operator_attention'}
    except Exception as exc:
        return {**base,'state':'browser_unavailable','error_type':type(exc).__name__}


async def _snapshot_locked(settings,platform,target,base,professional=False):
    async with BrowserSession(settings) as session:
        await asyncio.sleep(settings.platform_browser_delay_seconds)
        page,denied=await session.navigate(target)
        if denied:
            issue=getattr(session,'last_access_issue',{})
            if denied in {401,403,429,999}:
                blocked=record_hold(settings,platform,'http_'+str(denied),issue)
                return {**base,**blocked,'state':'operator_attention','http_status':denied}
            return {**base,'state':'not_found' if denied in {404,410} else 'public_profile_unavailable',
                    **issue,'http_status':denied}
        reader_name='professional-reader.js' if professional and platform=='linkedin.com' else 'platform-reader.js'
        reader=(Path(__file__).parent/'static'/reader_name).read_text(encoding='utf-8')
        result={'state':'fields_not_ready'}
        for _ in range(10):
            result=await page.evaluate(reader, {'includeExperience': settings.linkedin_profile_experience_enabled}) if professional and platform=='linkedin.com' else await page.evaluate(reader)
            if result['state']!='fields_not_ready':
                break
            await asyncio.sleep(1)
        if result['state']=='login_or_challenge':
            record_hold(settings,platform,'login_or_challenge')
        if result['state']!='captured':
            return {**base,**result}
        from .professionals import professional_target
        resolver=professional_target if professional else profile_target
        if resolver(result['url'])[1].rstrip('/')!=target.rstrip('/'):
            return {**base,'state':'redirect_identity_mismatch'}
        if professional and platform=='linkedin.com':
            from .social_browser import enrich_professional
            result = await enrich_professional(settings, session, target, result)
        from .discovery import official_root
        websites=[]
        for link in result['links']:
            try:
                root=official_root(link)
                if domain_of(root) not in {domain_of(w) for w in websites}:
                    websites.append(crawl_url(link))
            except ValueError:
                pass
        emails=[]
        for email in re.findall(EMAIL_RE,result['text']):
            try:
                emails.append(normalize_email(email))
            except ValueError:
                pass
        return {**base,**result,'sha256':hashlib.sha256(result['text'].encode()).hexdigest(),
                'outgoing_websites':websites,'public_links':result['links'],
                'published_emails':list(dict.fromkeys(emails)), 'published_email_links':result['mailto']}


async def browser_professional_snapshot(settings,url):
    from .professionals import professional_target
    platform,target=professional_target(url)
    base={'url':target,'capture_method':'managed_browser_professional_profile','scope':'visible_professional_fields',
          'observed_at':time.time(),'identity_verified':False}
    try:
        async with settings._platform_browser_lock:
            if blocked:=hold(settings,platform):
                return {**base,**blocked,'state':'operator_attention'}
            return await _snapshot_locked(settings,platform,target,base,professional=True)
    except LoginTransitionError:
        blocked=record_hold(settings,platform,'login_or_challenge')
        return {**base,**blocked,'state':'operator_attention'}
    except Exception as exc:
        return {**base,'state':'browser_unavailable','error_type':type(exc).__name__}


async def browser_discover(settings,platform,query,limit=10):
    from .providers import SearchRows
    if hold(settings,platform):
        return SearchRows([],[[platform,'operator_attention']])
    target=search_target(platform,query)
    try:
        async with settings._platform_browser_lock:
            if hold(settings,platform):
                return SearchRows([],[[platform,'operator_attention']])
            rows = await _discover_locked(settings,platform,target,limit)
            if platform == 'x.com' and not rows and settings.social_posts_enabled and not hold(settings, platform):
                post_target = 'https://x.com/search?' + urlencode({'q': query, 'f': 'live'})
                alternate = await _discover_locked(settings, platform, post_target, limit, post_search=True)
                return SearchRows(list(alternate), rows.engine_issues + alternate.engine_issues,
                                  rows.provider_reports + alternate.provider_reports)
            return rows
    except LoginTransitionError:
        record_hold(settings,platform,'login_or_challenge')
        return SearchRows([],[[platform,'login_or_challenge']])
    except Exception as exc:
        # Startup/lock/navigation errors are source failures, not empty success.
        return SearchRows([],[[platform,'browser_unavailable:'+type(exc).__name__]])


async def _discover_locked(settings,platform,target,limit,people=False,post_search=False):
    from .providers import SearchRows
    limit=max(1,min(200,int(limit)))
    found,issues={},[]
    coverage={'provider':'managed_browser:'+platform,'bounded':True,'snapshots':0,
              'scroll_actions':0,'next_page_actions':0,'duplicate_rows':0,'rejected_rows':0,
              'unique_results':0,'stop_reason':'step_budget','state':'partial'}
    async with BrowserSession(settings) as session:
        await asyncio.sleep(settings.platform_browser_delay_seconds)
        page,denied=await session.navigate(target)
        if denied:
            if denied in {401,403,429,999}:
                record_hold(settings,platform,'http_'+str(denied),getattr(session,'last_access_issue',{}))
            return SearchRows([],[[platform,'http_'+str(denied)]])
        reader_name = 'people-search-reader.js' if people else 'post-search-reader.js' if post_search else 'platform-search-reader.js'
        reader=(Path(__file__).parent/'static'/reader_name).read_text(encoding='utf-8')
        coverage['operation'] = 'people_search' if people else 'post_author_search' if post_search else 'company_profile_search'
        advance=(Path(__file__).parent/'static/platform-search-advance.js').read_text(encoding='utf-8')
        await page.bring_to_front()
        last_response=None
        def observe(response):
            nonlocal last_response
            if response.request.is_navigation_request() and response.frame==page.main_frame:
                last_response=response
        page.on('response',observe)
        stagnant=0
        try:
            async with asyncio.timeout(settings.platform_browser_search_timeout_seconds):
                for step in range(settings.platform_browser_search_steps):
                    result={'state':'fields_not_ready','rows':[]}
                    for _ in range(10):
                        if last_response and last_response.status>=400:
                            reason='http_'+str(last_response.status)
                            if last_response.status in {401,403,429,999}:
                                record_hold(settings,platform,reason,await response_issue(last_response))
                            result={'state':reason,'rows':[]}
                            break
                        if login_transition(target,page.url):
                            result={'state':'login_or_challenge','rows':[]}
                            break
                        if not search_identity_matches(target,page.url):
                            result={'state':'redirect_identity_mismatch','rows':[]}
                            break
                        try:
                            result=await page.evaluate(reader)
                        except Exception as exc:
                            result={'state':'reader_unavailable','rows':[],'error_type':type(exc).__name__}
                        if result['state'] not in {'fields_not_ready','reader_unavailable'}:
                            break
                        await asyncio.sleep(1)
                    coverage['snapshots']+=1
                    if result['state']!='captured':
                        coverage['stop_reason']=result['state']
                        issues.append([platform,result['state']])
                        if result['state']=='login_or_challenge':
                            record_hold(settings,platform,'login_or_challenge')
                        break
                    previous=len(found)
                    for row in result['rows'][:2000]:
                        try:
                            if people:
                                from .professionals import professional_target
                                route_platform,profile=professional_target(row['url'])
                            else:
                                route_platform,profile=profile_target(row['url'])
                            if route_platform!=platform or not row['title']:
                                raise ValueError('Unsupported search row')
                            source=profile.removesuffix('/about/') if platform=='linkedin.com' and not people else profile
                            if source in found:
                                coverage['duplicate_rows']+=1
                            elif len(found)<limit:
                                found[source]={**row,'url':source}
                        except (ValueError,TypeError,KeyError):
                            coverage['rejected_rows']+=1
                    if len(found)>=limit:
                        coverage.update(stop_reason='requested_limit',state='available')
                        break
                    stagnant=stagnant+1 if len(found)==previous else 0
                    if stagnant>=2:
                        coverage['stop_reason']='no_new_results'
                        break
                    if step+1>=settings.platform_browser_search_steps:
                        break
                    action=await page.evaluate(advance,{'allowNext':coverage['next_page_actions']+1<settings.platform_browser_search_pages})
                    if action['action'] not in {'scroll','next_page'}:
                        coverage['stop_reason']=action['action']
                        if action['action']=='login_or_challenge':
                            record_hold(settings,platform,'login_or_challenge')
                            issues.append([platform,'login_or_challenge'])
                        elif action['action']=='no_more_results':
                            coverage['state']='available'
                        break
                    coverage['scroll_actions' if action['action']=='scroll' else 'next_page_actions']+=1
                    if action['action']=='scroll':
                        # Native wheel input triggers lazy/virtualized result UI
                        # where a scripted scroll may not dispatch its load event.
                        await page.mouse.move(action['x'],action['y'])
                        await page.mouse.wheel(0,action['deltaY'])
                    await asyncio.sleep(max(.25,settings.platform_browser_delay_seconds))
        except TimeoutError:
            coverage['stop_reason']='deadline'
            issues.append([platform,'search_deadline'])
        except Exception as exc:
            coverage['stop_reason']='browser_error:'+type(exc).__name__
            issues.append([platform,coverage['stop_reason']])
        finally:
            page.remove_listener('response',observe)
        coverage['unique_results']=len(found)
        if not found and not issues:
            issues.append([platform,'no_visible_company_results'])
        return SearchRows(list(found.values()),issues,[coverage])


def search_identity_matches(target,current):
    """Pagination can change its page number, never platform/type/query identity."""
    try:
        expected,observed=urlsplit(target),urlsplit(current)
        if observed.scheme!='https' or observed.username or observed.password or observed.port:
            return False
        ehost,host=(expected.hostname or '').lower(),(observed.hostname or '').lower()
        if ehost=='linkedin.com' or ehost.endswith('.linkedin.com'):
            allowed=host=='linkedin.com' or host.endswith('.linkedin.com')
            key='keywords'
        else:
            allowed=host in {'x.com','www.x.com','twitter.com','www.twitter.com'}
            key='q'
        wanted,actual=parse_qs(expected.query),parse_qs(observed.query)
        return (allowed and observed.path.rstrip('/')==expected.path.rstrip('/')
                and actual.get(key)==wanted.get(key) and bool(wanted.get(key))
                and (key!='q' or wanted.get('f') in (['user'], ['live']) and actual.get('f')==wanted.get('f')))
    except ValueError:
        return False
