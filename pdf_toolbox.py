"""Desktop PDF merge and split tool that does not require administrator rights."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pypdf import PdfReader


class PdfToolboxApp(tk.Tk):
    """Tkinter desktop application for merging, splitting, and saving web content."""

    def __init__(self) -> None:
        super().__init__()
        self.title("PDF Toolbox - 統合・分割")
        self.geometry("860x620")
        self.minsize(800, 560)

        self.merge_files: list[Path] = []
        self.split_file: Path | None = None
        self.output_dir = tk.StringVar(value=str(Path.home() / "Desktop"))
        self.split_mode = tk.StringVar(value="pages")
        self.range_text = tk.StringVar(value="1-3,5")
        self.download_dir = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.download_status = tk.StringVar(value="URL を追加してダウンロードを開始してください。")
        self.file_type_vars: dict[str, tk.BooleanVar] = {}
        self.web_urls: list[str] = []

        self._build_ui()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        merge_tab = ttk.Frame(notebook, padding=12)
        split_tab = ttk.Frame(notebook, padding=12)
        download_tab = ttk.Frame(notebook, padding=12)
        notebook.add(merge_tab, text="PDF 統合")
        notebook.add(split_tab, text="PDF 分割")
        notebook.add(download_tab, text="Web ファイル保存")

        self._build_merge_tab(merge_tab)
        self._build_split_tab(split_tab)
        self._build_download_tab(download_tab)

    def _build_merge_tab(self, parent: ttk.Frame) -> None:
        instructions = "統合したい PDF を追加し、必要に応じて順番を変更してください。"
        ttk.Label(parent, text=instructions).pack(anchor=tk.W, pady=(0, 8))

        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.merge_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE)
        self.merge_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.merge_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.merge_listbox.configure(yscrollcommand=scrollbar.set)

        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="PDF を追加", command=self.add_merge_files).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="選択を削除", command=self.remove_merge_file).pack(side=tk.LEFT, padx=6)
        ttk.Button(button_frame, text="上へ", command=lambda: self.move_merge_file(-1)).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="下へ", command=lambda: self.move_merge_file(1)).pack(side=tk.LEFT, padx=6)
        ttk.Button(button_frame, text="すべてクリア", command=self.clear_merge_files).pack(side=tk.LEFT)

        ttk.Button(parent, text="統合 PDF を保存", command=self.merge_pdfs).pack(anchor=tk.E, pady=(8, 0))

    def _build_split_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="分割する PDF と出力フォルダーを選択してください。").pack(anchor=tk.W, pady=(0, 8))

        source_frame = ttk.Frame(parent)
        source_frame.pack(fill=tk.X, pady=4)
        self.split_file_label = ttk.Label(source_frame, text="PDF 未選択", relief=tk.SUNKEN, padding=6)
        self.split_file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(source_frame, text="PDF を選択", command=self.select_split_file).pack(side=tk.LEFT, padx=(8, 0))

        output_frame = ttk.Frame(parent)
        output_frame.pack(fill=tk.X, pady=4)
        ttk.Entry(output_frame, textvariable=self.output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="出力フォルダー", command=self.select_output_dir).pack(side=tk.LEFT, padx=(8, 0))

        mode_frame = ttk.LabelFrame(parent, text="分割方法", padding=10)
        mode_frame.pack(fill=tk.X, pady=12)

        ttk.Radiobutton(mode_frame, text="1ページずつ分割", variable=self.split_mode, value="pages").pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="ページ範囲で分割", variable=self.split_mode, value="ranges").pack(anchor=tk.W, pady=(6, 0))

        range_frame = ttk.Frame(mode_frame)
        range_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(range_frame, text="範囲:").pack(side=tk.LEFT)
        ttk.Entry(range_frame, textvariable=self.range_text).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Label(range_frame, text="例: 1-3,5,8-10").pack(side=tk.LEFT)

        ttk.Button(parent, text="PDF を分割", command=self.split_pdf).pack(anchor=tk.E, pady=(8, 0))

    def _build_download_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text="Web ページの URL を複数追加すると、選択した URL からファイル保存や PDF 保存を実行できます。",
        ).pack(anchor=tk.W, pady=(0, 8))

        url_frame = ttk.Frame(parent)
        url_frame.pack(fill=tk.X, pady=4)
        ttk.Label(url_frame, text="URL:").pack(side=tk.LEFT)
        self.web_url_entry = ttk.Entry(url_frame)
        self.web_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        ttk.Button(url_frame, text="追加", command=self.add_web_url).pack(side=tk.LEFT, padx=(8, 0))

        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.web_url_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, height=7)
        self.web_url_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.web_url_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.web_url_listbox.configure(yscrollcommand=scrollbar.set)

        url_button_frame = ttk.Frame(parent)
        url_button_frame.pack(fill=tk.X, pady=(6, 4))
        ttk.Button(url_button_frame, text="選択を削除", command=self.remove_selected_web_urls).pack(side=tk.LEFT)
        ttk.Button(url_button_frame, text="すべて選択", command=self.select_all_web_urls).pack(side=tk.LEFT, padx=6)
        ttk.Button(url_button_frame, text="すべてクリア", command=self.clear_web_urls).pack(side=tk.LEFT)

        output_frame = ttk.Frame(parent)
        output_frame.pack(fill=tk.X, pady=4)
        ttk.Entry(output_frame, textvariable=self.download_dir).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="保存フォルダー", command=self.select_download_dir).pack(side=tk.LEFT, padx=(8, 0))

        type_frame = ttk.LabelFrame(parent, text="取得するファイル形式（複数選択可）", padding=10)
        type_frame.pack(fill=tk.X, pady=(10, 0))
        for index, (key, config) in enumerate(FILE_TYPE_GROUPS.items()):
            variable = tk.BooleanVar(value=key in DEFAULT_FILE_TYPE_GROUPS)
            self.file_type_vars[key] = variable
            ttk.Checkbutton(type_frame, text=config["label"], variable=variable).grid(
                row=index // 3, column=index % 3, sticky=tk.W, padx=(0, 18), pady=2
            )

        ttk.Label(parent, textvariable=self.download_status, relief=tk.SUNKEN, padding=6).pack(fill=tk.X, pady=8)
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X)
        ttk.Button(action_frame, text="選択 URL のファイルリンクを一括ダウンロード", command=self.download_web_files).pack(side=tk.RIGHT)
        ttk.Button(action_frame, text="選択 URL のページ全体を PDF 保存", command=self.save_web_page_pdf).pack(side=tk.RIGHT, padx=(0, 8))

    def add_web_url(self) -> None:
        url = self.web_url_entry.get().strip()
        if not url:
            messagebox.showwarning("Web URL 追加", "追加する URL を入力してください。")
            return
        if url not in self.web_urls:
            self.web_urls.append(url)
            self.refresh_web_url_list()
        self.web_url_entry.delete(0, tk.END)

    def selected_web_urls(self) -> list[str]:
        selection = self.web_url_listbox.curselection()
        if not selection:
            return []
        return [self.web_urls[index] for index in selection]

    def remove_selected_web_urls(self) -> None:
        for index in reversed(self.web_url_listbox.curselection()):
            del self.web_urls[index]
        self.refresh_web_url_list()

    def select_all_web_urls(self) -> None:
        self.web_url_listbox.selection_set(0, tk.END)

    def clear_web_urls(self) -> None:
        self.web_urls.clear()
        self.refresh_web_url_list()

    def refresh_web_url_list(self) -> None:
        self.web_url_listbox.delete(0, tk.END)
        for url in self.web_urls:
            self.web_url_listbox.insert(tk.END, url)

    def select_download_dir(self) -> None:
        directory = filedialog.askdirectory(title="Web ファイルの保存フォルダー")
        if directory:
            self.download_dir.set(directory)

    def download_web_files(self) -> None:
        page_urls = self.selected_web_urls()
        if not page_urls:
            messagebox.showwarning("Web ファイル保存", "保存対象の URL を 1 つ以上選択してください。")
            return

        output_path = Path(self.download_dir.get()).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)

        try:
            extensions = selected_extensions(self.selected_file_type_groups())
            downloaded = download_file_links_for_pages(page_urls, output_path, extensions)
        except Exception as error:  # noqa: BLE001 - show actionable desktop error dialog
            messagebox.showerror("Web ファイル保存エラー", f"ファイルのダウンロードに失敗しました。\n{error}")
            return

        self.download_status.set(f"{len(page_urls)} URL から {downloaded} 件のファイルを保存しました: {output_path}")
        messagebox.showinfo("Web ファイル保存", f"{downloaded} 件のファイルを保存しました。")

    def selected_file_type_groups(self) -> list[str]:
        return [key for key, variable in self.file_type_vars.items() if variable.get()]

    def save_web_page_pdf(self) -> None:
        page_urls = self.selected_web_urls()
        if not page_urls:
            messagebox.showwarning("Web ページ PDF 保存", "PDF 保存対象の URL を 1 つ以上選択してください。")
            return

        output_dir = filedialog.askdirectory(title="Web ページ全体の PDF 保存フォルダー")
        if not output_dir:
            return

        try:
            saved_paths = save_web_pages_as_pdfs(page_urls, Path(output_dir))
        except Exception as error:  # noqa: BLE001 - show actionable desktop error dialog
            messagebox.showerror("Web ページ PDF 保存エラー", f"Web ページの PDF 保存に失敗しました。\n{error}")
            return

        self.download_status.set(f"{len(saved_paths)} 件の Web ページ全体を PDF 保存しました: {output_dir}")
        messagebox.showinfo("Web ページ PDF 保存", "Web ページ全体の PDF 保存が完了しました。")

    def add_merge_files(self) -> None:
        files = filedialog.askopenfilenames(title="統合する PDF を選択", filetypes=[("PDF files", "*.pdf")])
        for file_name in files:
            path = Path(file_name)
            if path not in self.merge_files:
                self.merge_files.append(path)
        self.refresh_merge_list()

    def remove_merge_file(self) -> None:
        selection = self.merge_listbox.curselection()
        if not selection:
            return
        del self.merge_files[selection[0]]
        self.refresh_merge_list()

    def move_merge_file(self, direction: int) -> None:
        selection = self.merge_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        new_index = index + direction
        if new_index < 0 or new_index >= len(self.merge_files):
            return
        self.merge_files[index], self.merge_files[new_index] = self.merge_files[new_index], self.merge_files[index]
        self.refresh_merge_list()
        self.merge_listbox.selection_set(new_index)

    def clear_merge_files(self) -> None:
        self.merge_files.clear()
        self.refresh_merge_list()

    def refresh_merge_list(self) -> None:
        self.merge_listbox.delete(0, tk.END)
        for path in self.merge_files:
            self.merge_listbox.insert(tk.END, str(path))

    def merge_pdfs(self) -> None:
        if len(self.merge_files) < 2:
            messagebox.showwarning("PDF 統合", "2つ以上の PDF を追加してください。")
            return

        save_path = filedialog.asksaveasfilename(
            title="統合 PDF の保存先",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not save_path:
            return

        try:
            from pypdf import PdfReader, PdfWriter

            writer = PdfWriter()
            for pdf_path in self.merge_files:
                reader = PdfReader(str(pdf_path))
                for page in reader.pages:
                    writer.add_page(page)
            with Path(save_path).open("wb") as output_file:
                writer.write(output_file)
        except Exception as error:  # noqa: BLE001 - show actionable desktop error dialog
            messagebox.showerror("PDF 統合エラー", f"PDF の統合に失敗しました。\n{error}")
            return

        messagebox.showinfo("PDF 統合", "PDF の統合が完了しました。")

    def select_split_file(self) -> None:
        file_name = filedialog.askopenfilename(title="分割する PDF を選択", filetypes=[("PDF files", "*.pdf")])
        if file_name:
            self.split_file = Path(file_name)
            self.split_file_label.configure(text=str(self.split_file))

    def select_output_dir(self) -> None:
        directory = filedialog.askdirectory(title="分割 PDF の出力フォルダー")
        if directory:
            self.output_dir.set(directory)

    def split_pdf(self) -> None:
        if self.split_file is None:
            messagebox.showwarning("PDF 分割", "分割する PDF を選択してください。")
            return

        output_path = Path(self.output_dir.get()).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)

        try:
            from pypdf import PdfReader

            reader = PdfReader(str(self.split_file))
            if self.split_mode.get() == "pages":
                self._split_each_page(reader, output_path)
            else:
                self._split_ranges(reader, output_path)
        except Exception as error:  # noqa: BLE001 - show actionable desktop error dialog
            messagebox.showerror("PDF 分割エラー", f"PDF の分割に失敗しました。\n{error}")
            return

        messagebox.showinfo("PDF 分割", "PDF の分割が完了しました。")

    def _split_each_page(self, reader: "PdfReader", output_dir: Path) -> None:
        stem = self.split_file.stem if self.split_file else "split"
        for index, page in enumerate(reader.pages, start=1):
            from pypdf import PdfWriter

            writer = PdfWriter()
            writer.add_page(page)
            self._write_pdf(writer, output_dir / f"{stem}_page_{index:03}.pdf")

    def _split_ranges(self, reader: "PdfReader", output_dir: Path) -> None:
        ranges = parse_page_ranges(self.range_text.get(), len(reader.pages))
        stem = self.split_file.stem if self.split_file else "split"
        for start, end in ranges:
            from pypdf import PdfWriter

            writer = PdfWriter()
            for page_index in range(start - 1, end):
                writer.add_page(reader.pages[page_index])
            self._write_pdf(writer, output_dir / f"{stem}_pages_{start}-{end}.pdf")

    @staticmethod
    def _write_pdf(writer: Any, path: Path) -> None:
        with path.open("wb") as output_file:
            writer.write(output_file)


FILE_TYPE_GROUPS = {
    "pdf": {"label": "PDF（.pdf）", "extensions": {".pdf"}},
    "word": {"label": "Word（.doc/.docx）", "extensions": {".doc", ".docx"}},
    "excel": {"label": "Excel/CSV（.xls/.xlsx/.csv）", "extensions": {".xls", ".xlsx", ".csv"}},
    "powerpoint": {"label": "PowerPoint（.ppt/.pptx）", "extensions": {".ppt", ".pptx"}},
    "text": {"label": "テキスト（.txt）", "extensions": {".txt"}},
    "image": {"label": "画像（jpg/png/gif/webp/svg）", "extensions": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}},
    "archive": {"label": "圧縮ファイル（zip/rar/7z/tar/gz）", "extensions": {".zip", ".rar", ".7z", ".tar", ".gz"}},
    "media": {"label": "動画・音声（mp4/mov/mp3等）", "extensions": {".mp3", ".wav", ".mp4", ".mov", ".avi", ".wmv"}},
    "installer": {"label": "実行/ディスクイメージ（exe/dmg/iso）", "extensions": {".exe", ".dmg", ".iso"}},
}
DEFAULT_FILE_TYPE_GROUPS = ("pdf", "word", "excel", "powerpoint")
FILE_LINK_EXTENSIONS = frozenset(
    extension
    for config in FILE_TYPE_GROUPS.values()
    for extension in config["extensions"]
)


class FileLinkParser(HTMLParser):
    """Collect href/src values that point to downloadable files."""

    def __init__(self, base_url: str, extensions: set[str] | frozenset[str] = FILE_LINK_EXTENSIONS) -> None:
        super().__init__()
        self.base_url = base_url
        self.extensions = {extension.lower() for extension in extensions}
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_names = ("href", "src") if tag in {"a", "source", "video", "audio", "img"} else ("href",)
        values = dict(attrs)
        for attr_name in attr_names:
            value = values.get(attr_name)
            if value and is_file_link(value, self.extensions):
                absolute_url = urljoin(self.base_url, value)
                if absolute_url not in self.links:
                    self.links.append(absolute_url)


def selected_extensions(selected_groups: list[str]) -> set[str]:
    """Return the file extensions represented by the selected file type groups."""
    extensions: set[str] = set()
    for group in selected_groups:
        config = FILE_TYPE_GROUPS.get(group)
        if config:
            extensions.update(config["extensions"])
    if not extensions:
        raise ValueError("取得するファイル形式を 1 つ以上選択してください。")
    return extensions


def is_file_link(url: str, extensions: set[str] | frozenset[str] = FILE_LINK_EXTENSIONS) -> bool:
    """Return True when a URL path looks like a direct downloadable file."""
    path = urlparse(url).path.lower()
    normalized_extensions = {extension.lower() for extension in extensions}
    return Path(path).suffix in normalized_extensions


def extract_file_links(
    html: str, base_url: str, extensions: set[str] | frozenset[str] = FILE_LINK_EXTENSIONS
) -> list[str]:
    """Extract unique absolute file links from an HTML document."""
    parser = FileLinkParser(base_url, extensions)
    parser.feed(html)
    return parser.links


def safe_download_name(url: str, used_names: set[str]) -> str:
    """Create a filesystem-safe unique filename from a URL."""
    parsed = urlparse(url)
    name = unquote(Path(parsed.path).name) or "download"
    name = re.sub(r'[^\w.()\- ]+', "_", name).strip(" .") or "download"
    stem = Path(name).stem or "download"
    suffix = Path(name).suffix
    candidate = name
    counter = 2
    while candidate in used_names:
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1
    used_names.add(candidate)
    return candidate


def safe_pdf_name(url: str, used_names: set[str]) -> str:
    """Create a filesystem-safe unique PDF filename from a page URL."""
    parsed = urlparse(url)
    base = parsed.netloc + parsed.path.rstrip("/")
    name = unquote(base.replace("/", "_")) or "web_page"
    name = re.sub(r'[^\w.()\- ]+', "_", name).strip(" ._") or "web_page"
    return safe_download_name(f"/{name}.pdf", used_names)


def download_file_links(
    page_url: str,
    output_dir: Path,
    extensions: set[str] | frozenset[str] = FILE_LINK_EXTENSIONS,
    used_names: set[str] | None = None,
) -> int:
    """Download every direct file link matching extensions found on a web page into output_dir."""
    request = Request(page_url, headers={"User-Agent": "PDF-Toolbox-Web-Downloader/1.0"})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - user-provided desktop utility URL
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")

    links = extract_file_links(html, page_url, extensions)
    used_download_names = used_names if used_names is not None else set()
    for link in links:
        target = output_dir / safe_download_name(link, used_download_names)
        file_request = Request(link, headers={"User-Agent": "PDF-Toolbox-Web-Downloader/1.0"})
        with urlopen(file_request, timeout=60) as response, target.open("wb") as output_file:  # noqa: S310
            output_file.write(response.read())
    return len(links)


def download_file_links_for_pages(
    page_urls: list[str], output_dir: Path, extensions: set[str] | frozenset[str] = FILE_LINK_EXTENSIONS
) -> int:
    """Download matching file links from multiple web pages into output_dir."""
    used_names: set[str] = set()
    return sum(download_file_links(page_url, output_dir, extensions, used_names) for page_url in page_urls)


def save_web_page_as_pdf(page_url: str, output_path: Path) -> None:
    """Render a web page in Chromium and save the complete page as a PDF."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "Web ページ全体の PDF 保存には playwright が必要です。"
            "requirements.txt を再インストールし、`python -m playwright install chromium` を実行してください。"
        ) from error

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(page_url, wait_until="networkidle", timeout=60_000)
            page.emulate_media(media="screen")
            page.pdf(path=str(output_path), format="A4", print_background=True)
        finally:
            browser.close()


def save_web_pages_as_pdfs(page_urls: list[str], output_dir: Path) -> list[Path]:
    """Render multiple web pages and save each complete page as a PDF in output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    saved_paths: list[Path] = []
    for page_url in page_urls:
        output_path = output_dir / safe_pdf_name(page_url, used_names)
        save_web_page_as_pdf(page_url, output_path)
        saved_paths.append(output_path)
    return saved_paths


def parse_page_ranges(range_text: str, page_count: int) -> list[tuple[int, int]]:
    """Parse one-based page ranges such as ``1-3,5,8-10``."""
    ranges: list[tuple[int, int]] = []
    for raw_part in range_text.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text.strip())
            end = int(end_text.strip())
        else:
            start = end = int(part)
        if start < 1 or end < start or end > page_count:
            raise ValueError(f"ページ範囲が不正です: {part}")
        ranges.append((start, end))
    if not ranges:
        raise ValueError("ページ範囲を入力してください。")
    return ranges


if __name__ == "__main__":
    app = PdfToolboxApp()
    app.mainloop()
