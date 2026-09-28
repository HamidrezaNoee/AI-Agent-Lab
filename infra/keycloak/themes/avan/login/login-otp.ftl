<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>آوان | تأیید هویت</title>
<link rel="stylesheet" href="${url.resourcesPath?html}/css/avan.css"></head>
<body class="avan-signin">
 <main class="signin-layout">
  <section class="signin-panel signin-otp" aria-labelledby="otp-heading">
   <div class="signin-brand"><span class="signin-mark" aria-hidden="true">آ</span><span>آوان<small>پلتفرم هوشمند سازمانی</small></span></div>
   <div class="signin-heading"><span class="signin-label">SECURE ACCESS</span><h1 id="otp-heading">تأیید هویت</h1>
    <p>کد برنامه Authenticator متصل به حساب خود را وارد کنید.</p></div>
   <#if message?has_content && message.type == 'error'><div class="signin-error" role="alert">${message.summary?html}</div></#if>
   <form id="kc-otp-login-form" action="${url.loginAction?html}" method="post">
    <#if otpLogin?? && otpLogin.userOtpCredentials?? && (otpLogin.userOtpCredentials?size > 1)>
      <label for="credentialId">دستگاه احراز هویت</label><select id="credentialId" name="credentialId"><#list otpLogin.userOtpCredentials as device><option value="${device.id?html}">${(device.userLabel!'Authenticator')?html}</option></#list></select>
    </#if>
    <label for="otp">کد شش‌رقمی Authenticator</label>
    <input id="otp" name="otp" type="text" inputmode="numeric" dir="ltr" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" placeholder="••••••" autofocus required>
    <button id="kc-login" type="submit">تأیید و ورود <span aria-hidden="true">←</span></button>
   </form>
   <p class="signin-footer">آوان · دسترسی ایمن سازمانی</p>
  </section>
  <div class="signin-art" aria-hidden="true"><div>✦<span>هوش در کنار تصمیم‌های شما</span></div></div>
 </main>
</body></html>
