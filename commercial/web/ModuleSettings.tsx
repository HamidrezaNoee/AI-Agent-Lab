import React, {useEffect, useState} from "react";

/** Optional UI for integration into a first-party authenticated host.
 * authorizedFetch MUST be the app's existing authenticated API fetch function.
 * No tokens, SQL passwords or checkout logic are stored in this component.
 * Showing a switch is NEVER an authorization check; API and SQL enforce access.
 */
export type CommercialModule = {
  module_code: number; key: string; title: string;
  licensed: boolean; enabled: boolean; active: boolean;
  license_until_utc: string | null;
};
type Props = {
  authorizedFetch: (path: string, init?: RequestInit) => Promise<Response>;
  isTenantAdmin: boolean;
};

export function ModuleSettings({authorizedFetch, isTenantAdmin}: Props) {
  const [modules, setModules] = useState<CommercialModule[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  async function refresh() {
    const response = await authorizedFetch("/v1/modules");
    if (!response.ok) throw new Error("دریافت وضعیت ماژول‌ها ناموفق بود.");
    const body = await response.json();
    setModules(body.modules as CommercialModule[]);
  }

  useEffect(() => {
    let alive = true;
    authorizedFetch("/v1/modules")
      .then(async r => {
        if (!r.ok) throw new Error("دسترسی به تنظیمات ماژول‌ها برقرار نیست.");
        return r.json();
      })
      .then(data => {if (alive) setModules(data.modules);})
      .catch(e => {if (alive) setError(String(e.message));});
    return () => {alive = false;};
  }, [authorizedFetch]);

  async function toggle(module: CommercialModule) {
    if (!isTenantAdmin || !module.licensed || module.module_code === 1) return;
    setBusy(module.module_code);
    setError("");
    try {
      const result = await authorizedFetch(
        `/v1/admin/modules/${module.module_code}`,
        {method:"PUT", headers:{"Content-Type":"application/json"},
         body:JSON.stringify({enabled:!module.enabled})},
      );
      if (!result.ok) throw new Error(
        result.status === 403
          ? "مجوز خرید معتبر یا دسترسی مدیریت این ماژول وجود ندارد."
          : "تغییر وضعیت ماژول انجام نشد."
      );
      await refresh(); // Always re-read actual DB state; never trust local switch.
    } catch (e) {
      setError(e instanceof Error ? e.message : "خطا در تغییر وضعیت");
    } finally {
      setBusy(null);
    }
  }

  return <section dir="rtl" aria-label="مدیریت ماژول‌های دستیار جلسات">
    <h2>مدیریت ماژول‌های هوشمند جلسات</h2>
    <p>ماژول پایه برای کاربران مجاز فعال است. سه ماژول اختیاری
       فقط با مجوز خرید معتبر و تأیید مدیر سازمان قابل فعال‌سازی‌اند.</p>
    {error && <p role="alert">{error}</p>}
    {modules.map(m => <article key={m.module_code}>
      <h3>{m.module_code}. {m.title}</h3>
      <p>{m.module_code === 1 ? "پایه" :
         !m.licensed ? "فاقد مجوز خرید معتبر" :
         m.active ? "فعال" : "غیرفعال"}</p>
      {m.module_code !== 1 && <button
        type="button" aria-pressed={m.active}
        disabled={!isTenantAdmin || !m.licensed || busy !== null}
        onClick={() => toggle(m)}
      >{busy === m.module_code ? "در حال ثبت..." :
         m.enabled ? "خاموش‌کردن ماژول" : "روشن‌کردن ماژول"}</button>}
    </article>)}
    <small>خرید، صدور مجوز و پرداخت در این پنل پیاده‌سازی نشده‌اند.
      این پنل فقط وضعیت ماژول‌های دارای مجوز را مدیریت می‌کند.</small>
  </section>;
}
