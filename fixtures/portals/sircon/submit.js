(function(){
  var params = new URLSearchParams(window.location.search);
  var drift = params.get('drift') === '1';
  var captcha = params.get('captcha') === '1';
  var required = ["legal_name","ein","npn","license_states"];
  if (drift) {
    document.getElementById('form-card').style.display = 'none';
    document.getElementById('drift-card').style.display = 'block';
    return;
  }
  if (captcha) {
    var div = document.createElement('div');
    div.className = 'g-recaptcha';
    div.setAttribute('data-sitekey', 'fixture-site-key');
    document.body.appendChild(div);
    var iframe = document.createElement('iframe');
    iframe.src = 'https://www.google.com/recaptcha/api2/anchor';
    iframe.title = 'recaptcha challenge';
    iframe.style.cssText = 'position:fixed;bottom:20px;right:20px;width:300px;height:80px;';
    document.body.appendChild(iframe);
  }
  document.getElementById('submission-form').addEventListener('submit', function(ev){
    ev.preventDefault();
    var data = {};
    new FormData(ev.target).forEach(function(v, k){ data[k] = v; });
    var missing = required.filter(function(r){ return !data[r] || String(data[r]).trim() === ''; });
    if (missing.length) {
      var e = document.getElementById('form-error');
      e.textContent = 'Missing required fields: ' + missing.join(', ');
      e.style.display = 'block';
      return;
    }
    var year = new Date().getUTCFullYear();
    var raw = Math.random().toString(36).slice(2, 10).toUpperCase();
    var rand = raw.replace(/[^A-Z0-9]/g, 'A');
    while (rand.length < 6) rand += 'A';
    var ref = 'SRC-' + year + '-' + rand;
    try { localStorage.setItem('lastConfirmation', ref); } catch (e) {}
    var qs = window.location.search ? (window.location.search + '&ref=' + ref) : ('?ref=' + ref);
    window.location.href = 'confirmation.html' + qs;
  });
})();
