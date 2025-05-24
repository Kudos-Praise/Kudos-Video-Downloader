import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import yt_dlp
from threading import Thread, Lock
import os
from PIL import Image, ImageTk
import requests
from io import BytesIO
import json
from queue import Queue
import time

class DownloadProgress:
    def __init__(self, url, format_id, parent):
        self.url = url
        self.format_id = format_id
        self.progress = 0
        self.status = "Pending"
        self.speed = "0 KB/s"
        self.eta = "Unknown"
        self.lock = Lock()
        
        # Create progress frame
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill=tk.X, padx=5, pady=2)
        
        # URL label (truncated)
        url_display = url[:50] + "..." if len(url) > 50 else url
        ttk.Label(self.frame, text=url_display).pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(self.frame, mode='determinate', length=200)
        self.progress_bar.pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_label = ttk.Label(self.frame, text="Pending")
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Speed and ETA
        self.info_label = ttk.Label(self.frame, text="0 KB/s | ETA: Unknown")
        self.info_label.pack(side=tk.LEFT, padx=5)

    def update(self, progress, status, speed=None, eta=None):
        with self.lock:
            self.progress = progress
            self.status = status
            if speed:
                self.speed = f"{speed:.1f} KB/s"
            if eta:
                minutes = eta // 60
                seconds = eta % 60
                self.eta = f"{minutes}:{seconds:02d}"
            
            # Update UI
            self.progress_bar['value'] = progress
            self.status_label['text'] = status
            self.info_label['text'] = f"{self.speed} | ETA: {self.eta}"

class VideoDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Downloader")
        self.root.geometry("800x600")
        
        # Main frame with padding
        main_frame = ttk.Frame(root, padding="3")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # URLs Frame - Compact
        url_frame = ttk.Frame(main_frame)
        url_frame.pack(fill=tk.X, pady=2)
        
        # URL input with button in same row
        input_frame = ttk.Frame(url_frame)
        input_frame.pack(fill=tk.X)
        
        self.urls_text = scrolledtext.ScrolledText(input_frame, height=3, width=60)
        self.urls_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Get Formats", command=self.fetch_formats).pack(fill=tk.X, pady=1)
        ttk.Button(btn_frame, text="Clear", command=lambda: self.urls_text.delete(1.0, tk.END)).pack(fill=tk.X, pady=1)
        
        # Location frame - Compact
        loc_frame = ttk.Frame(main_frame)
        loc_frame.pack(fill=tk.X, pady=2)
        ttk.Label(loc_frame, text="Save to:").pack(side=tk.LEFT)
        self.location_entry = ttk.Entry(loc_frame)
        self.location_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.location_entry.insert(0, os.path.expanduser("~/Downloads"))
        ttk.Button(loc_frame, text="...", width=3, command=self.browse_location).pack(side=tk.LEFT)
        
        # Downloads frame
        self.downloads_frame = ttk.Frame(main_frame)
        self.downloads_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Scrollable canvas for downloads
        self.canvas = tk.Canvas(self.downloads_frame)
        scrollbar = ttk.Scrollbar(self.downloads_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.formats = []
        self.downloading = False
        self.preview_window = None
        self.preview_image = None
        self.download_queue = Queue()
        self.active_downloads = {}
        self.max_concurrent_downloads = 3  # Maximum number of concurrent downloads

    def show_preview_window(self, video_info):
        if self.preview_window:
            self.preview_window.destroy()
        
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("Video Preview")
        self.preview_window.geometry("400x500")
        
        # Preview image
        try:
            response = requests.get(video_info['thumbnail'])
            img_data = Image.open(BytesIO(response.content))
            img_data = img_data.resize((360, 240), Image.Resampling.LANCZOS)
            self.preview_image = ImageTk.PhotoImage(img_data)
            
            img_label = ttk.Label(self.preview_window, image=self.preview_image)
            img_label.pack(pady=10)
        except Exception as e:
            ttk.Label(self.preview_window, text="Could not load preview image").pack(pady=10)
        
        # Video info
        info_frame = ttk.Frame(self.preview_window)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"Title: {video_info['title']}").pack(anchor='w')
        ttk.Label(info_frame, text=f"Duration: {video_info['duration']} seconds").pack(anchor='w')
        
        # Format selection
        format_frame = ttk.Frame(self.preview_window)
        format_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(format_frame, text="Select Format:").pack(anchor='w')
        
        # Create format options
        format_options = []
        for f in self.formats:
            if f.get('vcodec', 'none') != 'none' and f.get('acodec', 'none') != 'none':
                format_str = f"{f.get('format_note', '')} - {f.get('ext', '')} ({f.get('resolution', '')})"
                format_options.append((format_str, f['format_id']))
        
        self.format_var = tk.StringVar()
        format_combo = ttk.Combobox(format_frame, textvariable=self.format_var, values=[f[0] for f in format_options])
        format_combo.pack(fill=tk.X, pady=5)
        
        # Download button
        ttk.Button(self.preview_window, text="Add to Download Queue", 
                  command=lambda: self.add_to_queue(format_options[format_combo.current()][1] if format_combo.current() >= 0 else None)
                  ).pack(pady=10)

    def add_to_queue(self, format_id):
        if not format_id:
            messagebox.showwarning("Warning", "Please select a format")
            return
        
        urls = [url.strip() for url in self.urls_text.get(1.0, tk.END).splitlines() if url.strip()]
        if not urls:
            messagebox.showerror("Error", "Please enter at least one URL")
            return
        
        # Add all URLs to queue
        for url in urls:
            self.download_queue.put((url, format_id))
            progress = DownloadProgress(url, format_id, self.scrollable_frame)
            self.active_downloads[url] = progress
        
        self.preview_window.destroy()
        
        # Start download workers if not already running
        if not self.downloading:
            self.start_download_workers()

    def start_download_workers(self):
        self.downloading = True
        
        def download_worker():
            while not self.download_queue.empty() or self.downloading:
                try:
                    url, format_id = self.download_queue.get(timeout=1)
                    progress = self.active_downloads[url]
                    progress.update(0, "Downloading")
                    
                    try:
                        self.download_single_video(url, format_id, progress)
                        progress.update(100, "Completed")
                    except Exception as e:
                        progress.update(0, f"Failed: {str(e)}")
                    
                    self.download_queue.task_done()
                except:
                    time.sleep(0.1)
        
        # Start worker threads
        for _ in range(self.max_concurrent_downloads):
            Thread(target=download_worker, daemon=True).start()

    def download_single_video(self, url, format_id, progress):
        download_path = os.path.join(self.location_entry.get(), '%(title)s_%(id)s.%(ext)s')
        ydl_opts = {
            'format': format_id,
            'outtmpl': download_path,
            'progress_hooks': [lambda d: self.progress_hook(d, progress)],
            'retries': 10,
            'fragment_retries': 10,
            'continuedl': True,
            'socket_timeout': 30,
            'windowsfilenames': True,
            'ignoreerrors': True,
            'no_overwrites': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

    def progress_hook(self, d, progress):
        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes', 0)
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                if total > 0:
                    percentage = (downloaded / total) * 100
                    if speed:
                        speed = speed / 1024  # Convert to KB/s
                    progress.update(percentage, "Downloading", speed, eta)
            except:
                pass

    def fetch_formats(self):
        urls = [url.strip() for url in self.urls_text.get(1.0, tk.END).splitlines() if url.strip()]
        if not urls:
            messagebox.showerror("Error", "Please enter at least one URL")
            return
        
        self.formats = []
        ydl_opts = {
            'quiet': True,
            'no_warnings': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(urls[0], download=False)
                self.formats = info.get('formats', [])
                
                # Show preview window with format selection
                self.show_preview_window({
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', '')
                })
                
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def browse_location(self):
        directory = filedialog.askdirectory(
            initialdir=self.location_entry.get(),
            title="Select Download Location"
        )
        if directory:
            self.location_entry.delete(0, tk.END)
            self.location_entry.insert(0, directory)

if __name__ == '__main__':
    root = tk.Tk()
    app = VideoDownloaderGUI(root)
    root.mainloop()
