import os
import sys
import subprocess
import threading
import urllib.request
import zipfile
import shutil
import re
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

# Cấu hình giao diện CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
RCLONE_DIR = os.path.join(APP_DIR, "bin")
RCLONE_EXE = os.path.join(RCLONE_DIR, "rclone.exe")
RCLONE_CONF = os.path.join(APP_DIR, "rclone.conf")

ONEDRIVE_REMOTE = "onedrive_src"
GDRIVE_REMOTE = "gdrive_dst"

RCLONE_URL = "https://downloads.rclone.org/rclone-current-windows-amd64.zip"


class CloudTransferApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("OneDrive to Google Drive Transfer Tool")
        self.geometry("780x640")
        self.minsize(700, 580)

        # Đưa cửa sổ lên trên cùng khi vừa mở
        self.lift()
        self.attributes("-topmost", True)
        self.after(1500, lambda: self.attributes("-topmost", False))
        self.focus_force()

        self.transfer_process = None
        self.is_transferring = False

        self._build_ui()
        self.after(200, self._init_engine)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Header
        header_frame = ctk.CTkFrame(self, corner_radius=10)
        header_frame.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="CHUYỂN DỮ LIỆU ONEDRIVE ➔ GOOGLE DRIVE",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_lbl.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        sub_lbl = ctk.CTkLabel(
            header_frame,
            text="Đăng nhập trực tiếp qua trình duyệt Web • Sao chép giữ nguyên cấu trúc thư mục",
            font=ctk.CTkFont(size=12),
            text_color="gray75"
        )
        sub_lbl.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        # Bước 1: Kết nối tài khoản
        auth_frame = ctk.CTkFrame(self, corner_radius=10)
        auth_frame.grid(row=1, column=0, padx=16, pady=8, sticky="ew")
        auth_frame.grid_columnconfigure((0, 1), weight=1)

        step1_lbl = ctk.CTkLabel(
            auth_frame,
            text="1. Cấp quyền đăng nhập tài khoản (Qua trình duyệt Web)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        step1_lbl.grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 8), sticky="w")

        # OneDrive Box
        od_box = ctk.CTkFrame(auth_frame, fg_color="gray18", corner_radius=8)
        od_box.grid(row=1, column=0, padx=(16, 8), pady=(0, 14), sticky="ew")
        od_box.grid_columnconfigure(0, weight=1)

        self.od_status_lbl = ctk.CTkLabel(
            od_box, text="OneDrive: Chưa kết nối", font=ctk.CTkFont(size=13, weight="bold"), text_color="#f59e0b"
        )
        self.od_status_lbl.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        self.od_btn = ctk.CTkButton(
            od_box,
            text="Đăng nhập OneDrive (Web)",
            fg_color="#0078D4",
            hover_color="#005A9E",
            command=self.auth_onedrive
        )
        self.od_btn.grid(row=1, column=0, padx=12, pady=(4, 12), sticky="ew")

        # Google Drive Box
        gd_box = ctk.CTkFrame(auth_frame, fg_color="gray18", corner_radius=8)
        gd_box.grid(row=1, column=1, padx=(8, 16), pady=(0, 10), sticky="ew")
        gd_box.grid_columnconfigure(0, weight=1)

        self.gd_status_lbl = ctk.CTkLabel(
            gd_box, text="Google Drive: Chưa kết nối", font=ctk.CTkFont(size=13, weight="bold"), text_color="#f59e0b"
        )
        self.gd_status_lbl.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        self.gd_btn = ctk.CTkButton(
            gd_box,
            text="Đăng nhập Google Drive (Web)",
            fg_color="#107C41",
            hover_color="#0B532B",
            command=self.auth_gdrive
        )
        self.gd_btn.grid(row=1, column=0, padx=12, pady=(4, 12), sticky="ew")

        # Nút xuất cấu hình cho máy ảo GitHub Actions
        self.gh_btn = ctk.CTkButton(
            auth_frame,
            text="📋 Copy mã cấu hình (RCLONE_CONFIG) để chạy trên máy ảo GitHub Actions",
            fg_color="#374151",
            hover_color="#4b5563",
            command=self.copy_github_secret
        )
        self.gh_btn.grid(row=2, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="ew")

        # Bước 2: Đường dẫn thư mục
        path_frame = ctk.CTkFrame(self, corner_radius=10)
        path_frame.grid(row=2, column=0, padx=16, pady=8, sticky="ew")
        path_frame.grid_columnconfigure(1, weight=1)

        step2_lbl = ctk.CTkLabel(
            path_frame,
            text="2. Cấu hình thư mục Nguồn (OneDrive) và Đích (Google Drive)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        step2_lbl.grid(row=0, column=0, columnspan=3, padx=16, pady=(12, 8), sticky="w")

        ctk.CTkLabel(path_frame, text="Thư mục gốc OneDrive:").grid(row=1, column=0, padx=(16, 8), pady=6, sticky="w")
        self.src_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text="Để trống nếu muốn copy TOÀN BỘ OneDrive (VD: Documents/Work)"
        )
        self.src_entry.grid(row=1, column=1, columnspan=2, padx=(0, 16), pady=6, sticky="ew")

        ctk.CTkLabel(path_frame, text="Thư mục đích Google Drive:").grid(row=2, column=0, padx=(16, 8), pady=(6, 12), sticky="w")
        self.dst_entry = ctk.CTkEntry(
            path_frame,
            placeholder_text="Nhập tên thư mục trên Google Drive (VD: Backup_OneDrive)"
        )
        self.dst_entry.insert(0, "Backup_OneDrive")
        self.dst_entry.grid(row=2, column=1, columnspan=2, padx=(0, 16), pady=(6, 12), sticky="ew")

        # Bước 3: Điều khiển & Tiến trình
        ctrl_frame = ctk.CTkFrame(self, corner_radius=10)
        ctrl_frame.grid(row=3, column=0, padx=16, pady=(8, 16), sticky="nsew")
        ctrl_frame.grid_columnconfigure(0, weight=1)
        ctrl_frame.grid_rowconfigure(2, weight=1)

        btn_row = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        btn_row.grid(row=0, column=0, padx=16, pady=(12, 8), sticky="ew")
        btn_row.grid_columnconfigure((0, 1), weight=2)
        btn_row.grid_columnconfigure(2, weight=1)

        self.start_btn = ctk.CTkButton(
            btn_row,
            text="▶ CHẠY TRÊN MÁY NÀY",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self.start_transfer
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

        self.gh_run_btn = ctk.CTkButton(
            btn_row,
            text="☁ CHẠY TRÊN MÁY ẢO GITHUB",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            command=self.trigger_github_workflow
        )
        self.gh_run_btn.grid(row=0, column=1, padx=6, sticky="ew")

        self.stop_btn = ctk.CTkButton(
            btn_row,
            text="⏹ DỪNG LẠI",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#dc2626",
            hover_color="#b91c1c",
            state="disabled",
            command=self.stop_transfer
        )
        self.stop_btn.grid(row=0, column=2, padx=(6, 0), sticky="ew")

        # Progress bar & Status
        prog_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        prog_frame.grid(row=1, column=0, padx=16, pady=4, sticky="ew")
        prog_frame.grid_columnconfigure(0, weight=1)

        self.status_text = ctk.CTkLabel(prog_frame, text="Trạng thái: Đang kiểm tra công cụ nền...", anchor="w")
        self.status_text.grid(row=0, column=0, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(prog_frame)
        self.progress_bar.grid(row=1, column=0, pady=(4, 4), sticky="ew")
        self.progress_bar.set(0)

        # Log Box
        self.log_box = ctk.CTkTextbox(ctrl_frame, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.grid(row=2, column=0, padx=16, pady=(4, 14), sticky="nsew")

    def log(self, message: str):
        def _append():
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
        self.after(0, _append)

    def set_status(self, text: str, progress: float = None):
        def _update():
            self.status_text.configure(text=f"Trạng thái: {text}")
            if progress is not None:
                self.progress_bar.set(progress)
        self.after(0, _update)

    def _init_engine(self):
        threading.Thread(target=self._ensure_rclone, daemon=True).start()

    def _ensure_rclone(self):
        os.makedirs(RCLONE_DIR, exist_ok=True)
        if not os.path.exists(RCLONE_EXE):
            self.log("[*] Chưa tìm thấy rclone.exe. Đang tự động tải rclone chính thức cho Windows...")
            self.set_status("Đang tải engine truyền tải rclone...", 0.2)
            zip_path = os.path.join(RCLONE_DIR, "rclone.zip")
            try:
                req = urllib.request.Request(RCLONE_URL, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as out_f:
                    shutil.copyfileobj(resp, out_f)
                self.set_status("Đang giải nén rclone...", 0.6)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    for member in zf.namelist():
                        if member.endswith("rclone.exe"):
                            with zf.open(member) as source, open(RCLONE_EXE, "wb") as target:
                                shutil.copyfileobj(source, target)
                            break
                os.remove(zip_path)
                self.log("[+] Tải và cài đặt rclone.exe thành công!")
            except Exception as e:
                self.log(f"[!] Lỗi khi tải rclone: {e}")
                self.set_status("Lỗi tải công cụ nền!", 0)
                return

        self.refresh_remotes_status()
        self.set_status("Sẵn sàng. Hãy đăng nhập 2 tài khoản và nhấn Bắt đầu.", 0)

    def _run_rclone_cmd(self, args):
        cmd = [RCLONE_EXE, "--config", RCLONE_CONF] + args
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", startupinfo=startupinfo)

    def refresh_remotes_status(self):
        if not os.path.exists(RCLONE_EXE):
            return
        res = self._run_rclone_cmd(["listremotes"])
        remotes = [r.strip() for r in res.stdout.splitlines()]

        od_ok = f"{ONEDRIVE_REMOTE}:" in remotes
        gd_ok = f"{GDRIVE_REMOTE}:" in remotes

        def _ui_update():
            if od_ok:
                self.od_status_lbl.configure(text="OneDrive: ✔ Đã kết nối", text_color="#22c55e")
                self.od_btn.configure(text="Đổi tài khoản OneDrive")
            else:
                self.od_status_lbl.configure(text="OneDrive: Chưa kết nối", text_color="#f59e0b")
                self.od_btn.configure(text="Đăng nhập OneDrive (Web)")

            if gd_ok:
                self.gd_status_lbl.configure(text="Google Drive: ✔ Đã kết nối", text_color="#22c55e")
                self.gd_btn.configure(text="Đổi tài khoản Google Drive")
            else:
                self.gd_status_lbl.configure(text="Google Drive: Chưa kết nối", text_color="#f59e0b")
                self.gd_btn.configure(text="Đăng nhập Google Drive (Web)")

        self.after(0, _ui_update)
        return od_ok, gd_ok

    def auth_onedrive(self):
        if not os.path.exists(RCLONE_EXE):
            messagebox.showwarning("Chờ chút", "Công cụ nền đang được tải xuống, vui lòng đợi vài giây!")
            return
        threading.Thread(target=self._do_auth, args=(ONEDRIVE_REMOTE, "onedrive", "OneDrive"), daemon=True).start()

    def auth_gdrive(self):
        if not os.path.exists(RCLONE_EXE):
            messagebox.showwarning("Chờ chút", "Công cụ nền đang được tải xuống, vui lòng đợi vài giây!")
            return
        threading.Thread(target=self._do_auth, args=(GDRIVE_REMOTE, "drive", "Google Drive"), daemon=True).start()

    def copy_github_secret(self):
        od_ok, gd_ok = self.refresh_remotes_status()
        if not od_ok or not gd_ok:
            messagebox.showwarning(
                "Chưa kết nối đủ 2 tài khoản",
                "Bạn cần bấm Đăng nhập cả OneDrive và Google Drive trên tool này trước, sau đó mới copy mã cấu hình đưa lên máy ảo GitHub được!"
            )
            return
        if not os.path.exists(RCLONE_CONF):
            messagebox.showerror("Lỗi", "Không tìm thấy file rclone.conf!")
            return
        with open(RCLONE_CONF, "r", encoding="utf-8") as f:
            content = f.read()
        self.clipboard_clear()
        self.clipboard_append(content)
        self.update()
        self.log("\n[+] Đã copy toàn bộ nội dung rclone.conf vào Clipboard!")
        self.log("    👉 Hãy lên GitHub Repo -> Settings -> Secrets and variables -> Actions")
        self.log("    👉 Tạo New repository secret với Name: RCLONE_CONFIG và Paste (Ctrl+V) vào ô Secret.")
        messagebox.showinfo(
            "Đã Copy vào Clipboard",
            "Đã copy mã cấu hình thành công!\n\n"
            "Bây giờ bạn lên GitHub Repository của bạn:\n"
            "1. Vào Settings -> Secrets and variables -> Actions\n"
            "2. Bấm 'New repository secret'\n"
            "3. Đặt tên (Name) là: RCLONE_CONFIG\n"
            "4. Dán (Ctrl + V) nội dung vừa copy vào ô Secret."
        )

    def _do_auth(self, remote_name, remote_type, label):
        self.log(f"\n[*] Đang mở trình duyệt web để cấp quyền cho {label}...")
        self.log("    👉 Vui lòng đăng nhập và nhấn 'Allow' / 'Cho phép' trên trình duyệt vừa mở.")
        self.set_status(f"Đang chờ xác thực {label} trên trình duyệt web...")

        # Xóa cấu hình cũ nếu có
        self._run_rclone_cmd(["config", "delete", remote_name])

        cmd = [RCLONE_EXE, "--config", RCLONE_CONF, "config", "create", remote_name, remote_type]
        if remote_type == "drive":
            cmd += ["scope", "drive"]

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=startupinfo
        )

        for line in proc.stdout:
            line_str = line.strip()
            if line_str:
                self.log(f"  {line_str}")

        proc.wait()
        od_ok, gd_ok = self.refresh_remotes_status()
        if (remote_name == ONEDRIVE_REMOTE and od_ok) or (remote_name == GDRIVE_REMOTE and gd_ok):
            self.log(f"[+] Đã liên kết tài khoản {label} thành công!")
            self.set_status(f"Đã kết nối {label} thành công.")
        else:
            self.log(f"[!] Không thể xác thực {label}. Vui lòng thử lại.")
            self.set_status(f"Xác thực {label} thất bại.")

    def start_transfer(self):
        if self.is_transferring:
            return

        od_ok, gd_ok = self.refresh_remotes_status()
        if not od_ok or not gd_ok:
            messagebox.showerror(
                "Chưa đăng nhập đủ tài khoản",
                "Vui lòng nhấn nút Đăng nhập cho cả OneDrive và Google Drive trước khi bắt đầu copy!"
            )
            return

        src_sub = self.src_entry.get().strip().strip("/\\")
        dst_sub = self.dst_entry.get().strip().strip("/\\")

        src_remote_path = f"{ONEDRIVE_REMOTE}:{src_sub}" if src_sub else f"{ONEDRIVE_REMOTE}:"
        dst_remote_path = f"{GDRIVE_REMOTE}:{dst_sub}" if dst_sub else f"{GDRIVE_REMOTE}:"

        self.is_transferring = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_bar.set(0)

        self.log("\n" + "=" * 65)
        self.log(f"[*] BẮT ĐẦU SAO CHÉP DỮ LIỆU")
        self.log(f"    • Nguồn (OneDrive)    : {src_remote_path}")
        self.log(f"    • Đích (Google Drive) : {dst_remote_path}")
        self.log("=" * 65)

        threading.Thread(
            target=self._run_transfer_worker,
            args=(src_remote_path, dst_remote_path),
            daemon=True
        ).start()

    def _run_transfer_worker(self, src_path, dst_path):
        cmd = [
            RCLONE_EXE,
            "--config", RCLONE_CONF,
            "copy",
            src_path,
            dst_path,
            "--transfers", "4",
            "--checkers", "8",
            "--create-empty-src-dirs",
            "--stats", "1s",
            "--stats-one-line",
            "-P",
            "-v"
        ]

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            self.transfer_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo
            )

            pct_regex = re.compile(r"(\d+)%")

            for line in self.transfer_process.stdout:
                line_str = line.strip()
                if not line_str:
                    continue

                # Nếu là dòng thống kê tiến độ thì cập nhật lên thanh trạng thái
                if "Transferred:" in line_str or "%" in line_str:
                    match = pct_regex.search(line_str)
                    prog = float(match.group(1)) / 100.0 if match else None
                    self.set_status(line_str, prog)
                else:
                    self.log(line_str)

            rc = self.transfer_process.wait()
            if not self.is_transferring:
                self.log("\n[!] Đã dừng quá trình sao chép theo yêu cầu người dùng.")
                self.set_status("Đã hủy bởi người dùng.", 0)
            elif rc == 0:
                self.log("\n[✔] HOÀN TẤT SAO CHÉP TOÀN BỘ DỮ LIỆU THÀNH CÔNG!")
                self.set_status("Hoàn tất sao chép 100%!", 1.0)
                self.after(0, lambda: messagebox.showinfo("Hoàn tất", "Đã copy toàn bộ dữ liệu từ OneDrive sang Google Drive thành công!"))
            else:
                self.log(f"\n[!] Quá trình kết thúc với mã lỗi {rc}. Một số file có thể chưa được copy.")
                self.set_status(f"Có lỗi xảy ra (Mã: {rc}). Xem chi tiết ở khung Log.")

        except Exception as e:
            self.log(f"\n[!] Lỗi thực thi: {e}")
            self.set_status("Lỗi thực thi!")
        finally:
            self.is_transferring = False
            self.transfer_process = None
            self.after(0, lambda: self.start_btn.configure(state="normal"))
            self.after(0, lambda: self.stop_btn.configure(state="disabled"))

    def stop_transfer(self):
        if self.transfer_process and self.is_transferring:
            self.is_transferring = False
            try:
                self.transfer_process.terminate()
            except Exception:
                pass

    def trigger_github_workflow(self):
        od_ok, gd_ok = self.refresh_remotes_status()
        if not od_ok or not gd_ok:
            messagebox.showerror(
                "Chưa đăng nhập đủ tài khoản",
                "Vui lòng đăng nhập cả OneDrive và Google Drive trước!"
            )
            return

        src_sub = self.src_entry.get().strip().strip("/\\")
        dst_sub = self.dst_entry.get().strip().strip("/\\")
        threading.Thread(target=self._do_trigger_github, args=(src_sub, dst_sub), daemon=True).start()

    def _do_trigger_github(self, src_sub, dst_sub):
        import json
        import base64
        import webbrowser

        repo = "manhtien9x/onedrive-to-gdrive-runner"
        self.log(f"\n[*] Đang đồng bộ cấu hình và kích hoạt máy ảo GitHub ({repo})...")
        self.set_status("Đang gửi lệnh lên máy ảo GitHub Actions...")

        try:
            out = subprocess.check_output(
                ["git", "credential", "fill"],
                input=b"protocol=https\nhost=github.com\n"
            ).decode("utf-8", errors="replace")
            token = [line.split("=", 1)[1] for line in out.splitlines() if line.startswith("password=")][0]
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "CloudTransferApp"
            }

            # Cập nhật Secret RCLONE_CONFIG mới nhất nếu có pynacl
            try:
                from nacl import encoding, public
                req_key = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/public-key", headers=headers)
                key_data = json.loads(urllib.request.urlopen(req_key).read().decode())
                pub_key = public.PublicKey(key_data["key"].encode("utf-8"), encoding.Base64Encoder())
                sealed_box = public.SealedBox(pub_key)
                secret_val = open(RCLONE_CONF, "r", encoding="utf-8").read()
                encrypted = base64.b64encode(sealed_box.encrypt(secret_val.encode("utf-8"))).decode("utf-8")
                req_put = urllib.request.Request(
                    f"https://api.github.com/repos/{repo}/actions/secrets/RCLONE_CONFIG",
                    data=json.dumps({"encrypted_value": encrypted, "key_id": key_data["key_id"]}).encode(),
                    headers={**headers, "Content-Type": "application/json"},
                    method="PUT"
                )
                urllib.request.urlopen(req_put)
                self.log("[+] Đã tự động cập nhật Token đăng nhập mới nhất lên GitHub Secret.")
            except Exception as se:
                self.log(f"[*] Giữ nguyên Secret trên GitHub ({se})")

            # Gọi API workflow_dispatch
            dispatch_data = {
                "ref": "main",
                "inputs": {
                    "onedrive_src_path": src_sub,
                    "gdrive_dst_path": dst_sub,
                    "transfers": "8"
                }
            }
            req_dispatch = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/actions/workflows/transfer.yml/dispatches",
                data=json.dumps(dispatch_data).encode(),
                headers={**headers, "Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req_dispatch)

            actions_url = f"https://github.com/{repo}/actions"
            self.log(f"[✔] ĐÃ KÍCH HOẠT MÁY ẢO GITHUB THÀNH CÔNG!")
            self.log(f"    👉 Xem tiến trình trực tiếp tại: {actions_url}")
            self.set_status("Máy ảo GitHub đang chạy! Bạn có thể tắt máy tính.", 1.0)
            webbrowser.open(actions_url)

        except Exception as e:
            self.log(f"[!] Lỗi khi kích hoạt máy ảo GitHub: {e}")
            self.set_status("Lỗi kích hoạt GitHub Actions!")


if __name__ == "__main__":
    app = CloudTransferApp()
    app.mainloop()
