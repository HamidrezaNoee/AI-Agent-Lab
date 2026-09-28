<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>آوان | ورود</title>
<link rel="stylesheet" href="${url.resourcesPath?html}/css/avan.css"></head>
<body class="avan-signin">
 <main class="signin-layout">
  <section class="signin-panel" aria-labelledby="signin-heading">
   <div class="signin-brand"><span class="signin-mark" aria-hidden="true">آ</span><span>آوان<small>پلتفرم هوشمند سازمانی</small></span></div>
   <div class="signin-heading"><span class="signin-label">AVAN · AI AGENT</span><h1 id="signin-heading">ورود به فضای کار</h1></div>
   <#if message?has_content && message.type == 'error'><div class="signin-error" role="alert">${message.summary?html}</div></#if>
   <form id="kc-form-login" action="${url.loginAction?html}" method="post" autocomplete="on">
    <label for="username">نام کاربری</label>
    <input id="username" name="username" type="text" value="${(login.username!'')?html}" autocomplete="username" maxlength="256" autofocus required>
    <label for="password">رمز عبور</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required>
    <button id="kc-login" type="submit">ورود به آوان <span aria-hidden="true">←</span></button>
   </form>
  </section>
  <div class="signin-art" aria-hidden="true"></div>
 </main>
</body></html>
