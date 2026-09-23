"""LIMAK Meeting Agent License Studio — OFFLINE, Windows desktop/CLI.

Private issuer key NEVER belongs on any customer server, browser, GitHub,
ProcessMaker or public portal. Store it outside the source checkout and use
an encrypted PEM with a passphrase of at least 12 characters. No network calls.
"""
import argparse
from datetime import datetime, timezone, timedelta
from getpass import getpass
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from commercial.licensing.codec import (
    LicenseInvalid, make_payload, sign_license, verify_license,
)


def _protect_private_path(path: str) -> Path:
    target = Path(path).expanduser().resolve()
    checkout = Path(__file__).resolve().parents[2]
    if target == checkout or checkout in target.parents:
        raise ValueError("Private signing key MUST be outside the Git repository")
    if target.exists():
        raise ValueError("Refusing to overwrite an existing private key")
    if not target.parent.is_dir():
        raise ValueError("Private key folder does not exist")
    return target


def create_signer(private_path: str, public_path: str, passphrase: str) -> None:
    if not isinstance(passphrase,str) or len(passphrase) < 12:
        raise ValueError("Signing-key passphrase must contain at least 12 characters")
    private = _protect_private_path(private_path)
    public = Path(public_path).expanduser().resolve()
    if public.exists() or private == public or not public.parent.is_dir():
        raise ValueError("Public-key output must be a new distinct path")
    key = ec.generate_private_key(ec.SECP256R1())
    encrypted = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(passphrase.encode("utf-8")),
    )
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    fd = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(encrypted)
        with public.open("xb") as out:
            out.write(public_pem)
    except Exception:
        # On an incomplete keypair, never leave an unpaired private key behind.
        private.unlink(missing_ok=True)
        raise


def issue(*, private_path: str, output_path: str, password: str,
          tenant_id: str, installation_id: str, customer: str,
          max_users: int, modules: list[int], expires_at: str | None) -> dict:
    if not isinstance(password,str) or not password:
        raise ValueError("Signing-key passphrase required")
    out = Path(output_path).expanduser().resolve()
    if out.exists() or not out.parent.is_dir():
        raise ValueError("License output must be a new file in an existing folder")
    private = Path(private_path).expanduser().resolve()
    if not private.is_file():
        raise ValueError("Encrypted private signing key was not found")
    encrypted = private.read_bytes()
    if b"BEGIN ENCRYPTED PRIVATE KEY" not in encrypted:
        raise ValueError("Unencrypted signing keys are not accepted")
    key = serialization.load_pem_private_key(encrypted,
                                              password=password.encode("utf-8"))
    if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(
        key.curve, ec.SECP256R1
    ):
        raise ValueError("Expected issuer key: ECDSA P-256")
    payload = make_payload(tenant_id=tenant_id,installation_id=installation_id,
                           customer=customer,max_users=max_users,modules=modules,
                           expires_at=expires_at)
    token = sign_license(payload,key)
    with out.open("x",encoding="utf-8") as stream:
        stream.write(token+"\n")
    return {k:v for k,v in payload.items() if k!="signature"}


def expiry(days=None, expires='unlimited'):
    if days is not None:
        if type(days) is not int or not 1<=days<=36500:
            raise ValueError('License duration must be 1..36500 days')
        return (datetime.now(timezone.utc)+timedelta(days=days)).isoformat()
    return None if expires=='unlimited' else expires


def cli(args):
    if args.command=="keygen":
        pw=getpass("Signing-key passphrase (never stored): ")
        confirm=getpass("Repeat signing-key passphrase: ")
        if pw!=confirm:
            raise ValueError("Signing-key passphrases differ")
        create_signer(args.private,args.public,pw)
        print("PASS: encrypted offline LIMAK issuer private key and distributable public key created.")
    elif args.command=="issue":
        pw=getpass("Issuer private-key passphrase: ")
        payload=issue(private_path=args.private,output_path=args.out,password=pw,
                      tenant_id=args.tenant,installation_id=args.installation,
                      customer=args.customer,max_users=args.max_users,
                      modules=[int(x.strip()) for x in args.modules.split(",")],
                      expires_at=expiry(args.days, args.expires))
        print("PASS: tenant- and installation-bound ECDSA license generated.")
        print("License ID:",payload["license_id"],"Output:",args.out)
    elif args.command=="inspect":
        payload=verify_license(
            Path(args.license).read_text(encoding="utf-8").strip(),
            Path(args.public).read_bytes(),tenant_id=args.tenant,
            installation_id=args.installation,active_users=args.active_users,
        )
        print(json.dumps(payload,ensure_ascii=False,indent=2))
    else:
        launch_gui()


def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    app=tk.Tk()
    app.title("LIMAK License Studio — Meeting Agent")
    app.geometry("710x730")
    app.resizable(True,True)
    app.option_add("*Font",("Tahoma",10))
    main=ttk.Frame(app,padding=20)
    main.pack(fill="both",expand=True)
    ttk.Label(main,text="LIMAK | صدور لایسنس دستیار هوشمند جلسات",
              font=("Tahoma",14,"bold")).pack(anchor="e",pady=10)
    ttk.Label(main,text="این ابزار فقط روی سیستم امن صادرکننده اجرا می‌شود. کلید خصوصی و رمز را به مشتری ندهید.",
              wraplength=650).pack(anchor="e",pady=4)
    values={}
    def field(key,label,initial="",mask=False):
        row=ttk.Frame(main)
        row.pack(fill="x",pady=6)
        ttk.Label(row,text=label,width=30,anchor="e").pack(side="right")
        val=tk.StringVar(value=initial)
        ttk.Entry(row,textvariable=val,show="*" if mask else "",
                  width=55).pack(side="right",fill="x",expand=True)
        values[key]=val
    field("private","فایل کلید خصوصی رمزدار (.pem)")
    field("public","فایل کلید عمومی (.pem)")
    field("password","رمز کلید صادرکننده",mask=True)
    field("tenant","شناسه UUID سازمان")
    field("installation","Installation ID شصت‌وچهاررقمی")
    field("customer","نام شرکت مشتری")
    field("max_users","حداکثر کاربران فعال","100")
    field("modules","ماژول‌های مجاز، جداشده با ویرگول","1,2,3,4")
    field("days","مدت اعتبار (روز، برای تاریخ دقیق خالی)","365")
    field("expires","تاریخ دقیق ISO یا unlimited (در صورت خالی‌بودن روز)","unlimited")
    field("output","مسیر فایل لایسنس خروجی")
    def choose(key,save=False):
        selected=(filedialog.asksaveasfilename(defaultextension=".license.txt")
                  if save else filedialog.askopenfilename())
        if selected: values[key].set(selected)
    ttk.Button(main,text="انتخاب کلید خصوصی",command=lambda:choose("private")).pack(anchor="w")
    ttk.Button(main,text="انتخاب کلید عمومی",command=lambda:choose("public")).pack(anchor="w")
    ttk.Button(main,text="انتخاب محل ذخیره لایسنس",command=lambda:choose("output",True)).pack(anchor="w")
    def create_keys():
        try:
            create_signer(values["private"].get(),values["public"].get(),
                          values["password"].get())
            messagebox.showinfo("موفق","کلید خصوصی رمزدار و کلید عمومی ایجاد شدند. کلید خصوصی را خارج از مخزن نگه دارید.")
        except Exception as exc:
            messagebox.showerror("خطا",str(exc))
    def generate():
        try:
            payload=issue(private_path=values["private"].get(),
               output_path=values["output"].get(),password=values["password"].get(),
               tenant_id=values["tenant"].get(),installation_id=values["installation"].get(),
               customer=values["customer"].get(),
               max_users=int(values["max_users"].get()),
               modules=[int(x.strip()) for x in values["modules"].get().split(",")],
               expires_at=expiry(int(values["days"].get()) if values["days"].get().strip() else None, values["expires"].get()))
            messagebox.showinfo("صدور موفق","لایسنس امضاشده ذخیره شد.\nLicense ID: "+payload["license_id"])
        except Exception as exc:
            messagebox.showerror("خطا",str(exc))
    ttk.Button(main,text="ساخت کلید امن (فقط یک بار)",command=create_keys).pack(fill="x",pady=10)
    ttk.Button(main,text="صدور لایسنس امضاشده",command=generate).pack(fill="x",pady=10)
    app.mainloop()


def main():
    parser=argparse.ArgumentParser(description="LIMAK Meeting Agent OFFLINE License Studio")
    sub=parser.add_subparsers(dest="command")
    k=sub.add_parser("keygen");k.add_argument("--private",required=True);k.add_argument("--public",required=True)
    i=sub.add_parser("issue")
    for arg in ("private","tenant","installation","customer","out"):
        i.add_argument("--"+arg,required=True)
    i.add_argument("--max-users",type=int,required=True)
    i.add_argument("--modules",default="1")
    term=i.add_mutually_exclusive_group()
    term.add_argument("--expires",default="unlimited")
    term.add_argument("--days",type=int)
    inspect=sub.add_parser("inspect")
    for arg in ("public","license","tenant","installation"):
        inspect.add_argument("--"+arg,required=True)
    inspect.add_argument("--active-users",type=int,default=0)
    args=parser.parse_args()
    try:
        cli(args)
    except (ValueError,LicenseInvalid,TypeError,OSError) as exc:
        parser.exit(2,"License operation failed: "+str(exc)+"\n")


if __name__=="__main__":
    main()

