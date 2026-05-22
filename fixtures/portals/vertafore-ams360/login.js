(function(){
  var params = new URLSearchParams(window.location.search);
  var forceAuthFail = params.get('auth_fail') === '1';
  var captcha = params.get('captcha') === '1';
  if (captcha) {
    var iframe = document.createElement('iframe');
    iframe.src = 'https://www.google.com/recaptcha/api2/anchor';
    iframe.title = 'recaptcha';
    iframe.style.cssText = 'position:fixed;bottom:20px;right:20px;width:300px;height:80px;border:1px solid #ccc';
    document.body.appendChild(iframe);
  }
  document.getElementById('login-form').addEventListener('submit', function(ev){
    ev.preventDefault();
    var u = document.getElementById('username').value;
    var p = document.getElementById('password').value;
    if (forceAuthFail || u !== 'demo' || p !== 'demo') {
      document.getElementById('auth-error').style.display = 'block';
      window.history.replaceState({}, '', window.location.pathname + '?denied=1');
      return;
    }
    var qs = window.location.search || '';
    window.location.href = 'dashboard.html' + qs;
  });
})();
