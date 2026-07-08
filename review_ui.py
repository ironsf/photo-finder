from __future__ import annotations

import threading
import webbrowser
from io import BytesIO
from tkinter import Button, Entry, Frame, Label, StringVar, Tk

from PIL import Image, ImageTk

import config
import image_proc
import search
import state
from excel_reader import read_products

PREVIEW_SIZE = (480, 480)


class ReviewApp:
    def __init__(self, products):
        self.products = products
        self.product_idx = 0
        self.candidates = []
        self.candidate_idx = 0
        self._thumb_cache = {}
        self._photo = None
        self._auto_accept_job = None
        self.report = state.load_report()
        # Ленивая догрузка: план (провайдер, запрос) + позиция + уже показанные URL
        self._plan = []
        self._plan_idx = 0
        self._seen_urls = set()

        self.root = Tk()
        self.root.title("photoFinder — проверка")
        self.root.geometry("640x760")

        self.counter_var = StringVar()
        self.barcode_var = StringVar()
        self.name_text_var = StringVar()
        self.status_var = StringVar()
        self.auto_var = StringVar()
        self.toast_var = StringVar()
        self._toast_job = None

        bg = self.root.cget("bg")

        Label(self.root, textvariable=self.counter_var, font=("Arial", 10)).pack(pady=(10, 0))
        self.image_label = Label(self.root)
        self.image_label.pack(pady=10)

        # Штрихкод — кликабельный (копируется по клику) и выделяемый мышью.
        self.barcode_entry = Entry(
            self.root,
            textvariable=self.barcode_var,
            state="readonly",
            justify="center",
            font=("Arial", 15, "bold"),
            fg="#0b66c3",
            readonlybackground=bg,
            relief="flat",
            bd=0,
            cursor="hand2",
        )
        self.barcode_entry.pack(pady=(0, 2))
        self.barcode_entry.bind("<Button-1>", lambda e: self.copy_barcode())
        Label(
            self.root,
            text="(клик по штрихкоду — скопировать)",
            font=("Arial", 8),
            fg="gray",
        ).pack()

        # Название — выделяется и копируется (Ctrl+C).
        name_entry = Entry(
            self.root,
            textvariable=self.name_text_var,
            state="readonly",
            justify="center",
            font=("Arial", 12),
            readonlybackground=bg,
            relief="flat",
            bd=0,
        )
        name_entry.pack(fill="x", padx=20, pady=(4, 0))

        Label(self.root, textvariable=self.toast_var, font=("Arial", 9, "bold"), fg="#1a7f37").pack(pady=(2, 0))
        Label(self.root, textvariable=self.status_var, font=("Arial", 9), fg="gray").pack(pady=(0, 4))
        Label(self.root, textvariable=self.auto_var, font=("Arial", 10, "bold"), fg="#1a7f37").pack(pady=(0, 6))

        btn_frame = Frame(self.root)
        btn_frame.pack(pady=10)
        Button(btn_frame, text="← Назад [B]", width=12, command=self.on_back).grid(row=0, column=0, padx=4)
        Button(btn_frame, text="✕ Нет [N]", width=12, command=self.on_reject).grid(row=0, column=1, padx=4)
        Button(btn_frame, text="✓ Да [Y]", width=12, command=self.on_accept).grid(row=0, column=2, padx=4)
        Button(btn_frame, text="Пропустить [S]", width=14, command=self.on_skip).grid(row=0, column=3, padx=4)
        Button(self.root, text="Открыть в браузере", command=self.on_open_browser).pack(pady=(0, 10))

        self.root.bind("y", lambda e: self.on_accept())
        self.root.bind("<Return>", lambda e: self.on_accept())
        self.root.bind("n", lambda e: self.on_reject())
        self.root.bind("<Right>", lambda e: self.on_reject())
        self.root.bind("b", lambda e: self.on_back())
        self.root.bind("<Left>", lambda e: self.on_back())
        self.root.bind("s", lambda e: self.on_skip())
        self.root.bind("<Escape>", lambda e: self.on_quit())
        self.root.protocol("WM_DELETE_WINDOW", self.on_quit)

        self.load_current_product()

    def current_product(self):
        return self.products[self.product_idx]

    def _fetch_next_batch(self):
        """Следующий шаг плана: догружаем кандидатов, отсеивая уже показанные.

        Возвращает список новых (ранжированных) кандидатов или [] если план исчерпан.
        Может бросить QuotaExceededError.
        """
        code, name = self.current_product()
        while self._plan_idx < len(self._plan):
            fn, query = self._plan[self._plan_idx]
            self._plan_idx += 1
            raw = fn(query)
            fresh = [c for c in raw if c["image_url"] not in self._seen_urls]
            if not fresh:
                continue
            for c in fresh:
                self._seen_urls.add(c["image_url"])
            return search.rank_batch(fresh, name)
        return []

    def load_current_product(self):
        while self.product_idx < len(self.products):
            code, name = self.current_product()
            out_path = config.OUTPUT_DIR / f"{code}.jpg"
            if out_path.exists() or state.is_resolved(code, self.report):
                self.product_idx += 1
                continue
            self._plan = search.build_search_plan(code, name)
            self._plan_idx = 0
            self._seen_urls = set()
            self.candidate_idx = 0
            try:
                self.candidates = self._fetch_next_batch()
            except state.QuotaExceededError as e:
                self.stop_on_quota(str(e))
                return
            if not self.candidates:
                print(f"[notfound] {code} — нет кандидатов")
                state.append_row(state.make_row(code, name, "notfound"))
                self.product_idx += 1
                continue
            if all(c.get("too_small") for c in self.candidates):
                print(f"[no-large] {code} — крупных фото не найдено, показываю только мелкие")
            self.show_candidate()
            return
        self.finish()

    def show_candidate(self):
        self._cancel_auto_accept()
        code, name = self.current_product()
        total = len(self.products)
        n_candidates = len(self.candidates)
        self.counter_var.set(
            f"Товар {self.product_idx + 1}/{total} · кандидат {self.candidate_idx + 1}/{n_candidates}"
        )
        self.barcode_var.set(code)
        self.name_text_var.set(name)

        candidate = self.candidates[self.candidate_idx]
        parts = []
        domain = candidate.get("domain", "")
        if domain:
            parts.append(domain)
        score = candidate.get("relevance")
        if score is not None:
            parts.append(f"релевантность {score:.0%}")
        width, height = candidate.get("width"), candidate.get("height")
        if width and height:
            parts.append(f"{width}×{height}px")
        if self._is_too_small(candidate):
            parts.append("⚠ малое разрешение (крупнее не нашлось)")
        self.status_var.set(" · ".join(parts))
        self.render_image(candidate["thumbnail_url"] or candidate["image_url"])
        self.prefetch_next()

        if (
            score is not None
            and score >= config.AUTO_ACCEPT_THRESHOLD
            and not self._is_too_small(candidate)
        ):
            self._run_auto_accept_countdown(config.AUTO_ACCEPT_DELAY_SECONDS)

    @staticmethod
    def _is_too_small(candidate):
        if candidate.get("too_small"):
            return True
        width, height = candidate.get("width"), candidate.get("height")
        if not width or not height:
            return False
        return max(width, height) < config.MIN_IMAGE_DIMENSION

    def copy_barcode(self):
        code = self.barcode_var.get().strip()
        if not code:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self._show_toast("✓ Скопировано в буфер обмена")

    def _show_toast(self, text):
        self.toast_var.set(text)
        if self._toast_job is not None:
            self.root.after_cancel(self._toast_job)
        self._toast_job = self.root.after(1500, lambda: self.toast_var.set(""))

    def render_image(self, url):
        try:
            raw = self._thumb_cache.get(url) or image_proc.download_image(url)
            self._thumb_cache[url] = raw
            img = Image.open(BytesIO(raw))
            img.thumbnail(PREVIEW_SIZE)
            self._photo = ImageTk.PhotoImage(img)
            self.image_label.configure(image=self._photo, text="")
        except Exception as e:
            self.image_label.configure(image="", text=f"[ошибка загрузки превью: {e}]")

    def prefetch_next(self):
        if self.candidate_idx + 1 >= len(self.candidates):
            return
        next_url = self.candidates[self.candidate_idx + 1]["thumbnail_url"]
        if not next_url or next_url in self._thumb_cache:
            return

        def _worker():
            try:
                self._thumb_cache[next_url] = image_proc.download_image(next_url)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _run_auto_accept_countdown(self, seconds_left):
        if seconds_left <= 0:
            self.auto_var.set("")
            self.on_accept(auto=True)
            return
        self.auto_var.set(
            f"✓ Высокая уверенность — автопринятие через {seconds_left}с "
            "(нажмите любую клавишу для отмены)"
        )
        self._auto_accept_job = self.root.after(
            1000, lambda: self._run_auto_accept_countdown(seconds_left - 1)
        )

    def _cancel_auto_accept(self):
        if self._auto_accept_job is not None:
            self.root.after_cancel(self._auto_accept_job)
            self._auto_accept_job = None
        self.auto_var.set("")

    def on_accept(self, auto=False):
        self._cancel_auto_accept()
        code, name = self.current_product()
        candidate = self.candidates[self.candidate_idx]
        try:
            path, info = image_proc.process_candidate(candidate["image_url"], code)
            tag = "[auto-done]" if auto else "[done]"
            print(f"{tag} {code} -> {path.name} ({info['final_size']}, low_res={info['low_res']})")
            state.append_row(state.make_row(code, name, "done", candidate, info, auto_accepted=auto))
        except Exception as e:
            print(f"[error] {code}: {e}")
            state.append_row(state.make_row(code, name, "error", candidate, error_msg=str(e)))
        self.product_idx += 1
        self.load_current_product()

    def on_reject(self):
        self._cancel_auto_accept()
        if self.candidate_idx + 1 < len(self.candidates):
            self.candidate_idx += 1
            self.show_candidate()
            return
        # Кандидаты кончились — пробуем догрузить следующий источник/запрос.
        code, name = self.current_product()
        try:
            more = self._fetch_next_batch()
        except state.QuotaExceededError as e:
            self.stop_on_quota(str(e))
            return
        if more:
            self.candidates.extend(more)
            self.candidate_idx += 1
            self.show_candidate()
        else:
            print(f"[notfound] {code} — кандидаты закончились")
            state.append_row(state.make_row(code, name, "notfound"))
            self.product_idx += 1
            self.load_current_product()

    def on_back(self):
        self._cancel_auto_accept()
        if self.candidate_idx > 0:
            self.candidate_idx -= 1
            self.show_candidate()

    def on_skip(self):
        self._cancel_auto_accept()
        code, name = self.current_product()
        print(f"[skipped] {code}")
        state.append_row(state.make_row(code, name, "skipped"))
        self.product_idx += 1
        self.load_current_product()

    def on_open_browser(self):
        self._cancel_auto_accept()
        if self.candidates:
            webbrowser.open(self.candidates[self.candidate_idx]["page_url"])

    def on_quit(self):
        self._cancel_auto_accept()
        self.root.destroy()

    def finish(self):
        self.barcode_var.set("")
        self.name_text_var.set("Готово — товары закончились")
        self.counter_var.set("")
        self.status_var.set("")
        self.image_label.configure(image="", text="")
        self._photo = None

    def stop_on_quota(self, message: str):
        self.barcode_var.set("")
        self.name_text_var.set(message)
        self.counter_var.set("")
        self.status_var.set("")
        self.image_label.configure(image="", text="")
        self._photo = None

    def run(self):
        self.root.mainloop()


def main():
    products = read_products(config.INPUT_XLSX, config.BARCODE_COL, config.NAME_COL, config.HAS_HEADER)
    app = ReviewApp(products)
    app.run()


if __name__ == "__main__":
    main()
