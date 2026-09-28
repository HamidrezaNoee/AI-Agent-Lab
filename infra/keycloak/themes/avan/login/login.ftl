<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>آوان | ورود</title>
<link rel="stylesheet" href="${url.resourcesPath?html}/css/avan.css"></head>
<body class="avan-signin">
 <main class="signin-layout">
  <section class="signin-panel" aria-labelledby="signin-heading">
   <div class="signin-brand"><span class="signin-mark" aria-hidden="true">آ</span><span>آوان<small>پلتفرم هوشمند سازمانی</small></span></div>
   <div class="signin-heading"><span class="signin-label">AVAN · AI AGENT</span><h1 id="signin-heading">ورود به فضای کار</h1>
    <p>با حساب سازمانی خود وارد شوید.</p></div>
   <#if message?has_content && message.type == 'error'><div class="signin-error" role="alert">${message.summary?html}</div></#if>
   <form id="kc-form-login" action="${url.loginAction?html}" method="post" autocomplete="on">
    <label for="username">نام کاربری</label>
    <input id="username" name="username" type="text" value="${(login.username!'')?html}" autocomplete="username" maxlength="256" autofocus required>
    <label for="password">رمز عبور</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required>
    <#if avanCaptchaImage??>
    <label for="avan_captcha">کد امنیتی تصویر</label>
    <div class="signin-captcha"><img src="${avanCaptchaImage?html}" width="260" height="85" alt="کد امنیتی شش کاراکتری" draggable="false">
      <input id="avan_captcha" name="avan_captcha" type="text" inputmode="latin" dir="ltr" autocomplete="off" minlength="6" maxlength="6" pattern="[2-9A-HJ-NP-Za-hj-np-z]{6}" autocapitalize="characters" spellcheck="false" required aria-label="کد امنیتی تصویر" placeholder="کد تصویر"></div>
    </#if>
    <button id="kc-login" type="submit">ورود به آوان <span aria-hidden="true">←</span></button>
   </form>
   <p class="signin-footer">آوان · تصمیم‌های روشن با هوش سازمانی</p>
  </section>
  <div class="signin-art" aria-hidden="true"><div>✦<span>هوش در کنار تصمیم‌های شما</span></div></div>
 </main>
</body></html>
