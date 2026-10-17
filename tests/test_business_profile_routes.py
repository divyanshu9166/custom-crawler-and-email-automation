"""A job, category or search result cannot establish website-less company identity."""
import pytest

from outreach.profiles import canonical_profile


@pytest.mark.parametrize('url', [
    'https://www.peopleperhour.com/freelance-jobs/technology-programming/website-development/uk-applicant-only-website-development-4524254',
    'https://www.peopleperhour.com/freelance-jobs/technology-programming/website-development',
    'https://www.peopleperhour.com/freelancers',
    'https://clutch.co/web-developers',
    'https://crunchbase.com/hub/london-companies',
    'https://trustpilot.com/categories/beauty',
    'https://yelp.com/search?find_desc=plumbers',
    'https://www.bbb.org/us/co/denver/category/roofing-contractors',
])
def test_non_business_routes_are_rejected(url):
    with pytest.raises(ValueError, match='specific public business profile'):
        canonical_profile(url)


@pytest.mark.parametrize('url', [
    'https://www.peopleperhour.com/freelancer/design/acme-studio-example-id',
    'https://clutch.co/profile/acme-studio',
    'https://crunchbase.com/organization/acme-studio',
    'https://trustpilot.com/review/acme.example',
    'https://yelp.com/biz/acme-studio-denver',
    'https://www.bbb.org/us/tx/lago-vista/profile/plumber/real-texas-plumbing-llc-0825-1000163531',
])
def test_specific_profiles_are_only_candidates_requiring_review(url):
    assert canonical_profile(url) == url
