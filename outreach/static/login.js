document.querySelector('#login-form').addEventListener('submit',async event=>{
  event.preventDefault();const form=event.currentTarget,button=form.querySelector('button'),error=document.querySelector('#login-error');
  button.disabled=true;error.textContent='';
  try{const response=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(form)))});
    if(!response.ok){const data=await response.json();throw new Error(data.detail||'Sign in failed');}location.replace('/');
  }catch(e){error.textContent=e.message;}finally{button.disabled=false;}
});
