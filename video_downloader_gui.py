import tkinter as tk
from tkinter import ttk, messagebox
import yt_dlp
from threading import Thread

class VideoDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Downloader")
        self.root.geometry("800x600")
        
        # URL Entry
        url_frame = ttk.Frame(root, padding="10")
        url_frame.pack(fill=tk.X)
        
        ttk.Label(url_frame, text="Video URL:").pack(side=tk.LEFT)
        self.url_entry = ttk.Entry(url_frame, width=50)
        self.url_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(url_frame, text="Get Formats", command=self.fetch_formats).pack(side=tk.LEFT, padx=5)
        
        # Formats Display
        formats_frame = ttk.Frame(root, padding="10")
        formats_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview for formats
        columns = ("Format ID", "Extension", "Resolution", "Filesize", "Note")
        self.tree = ttk.Treeview(formats_frame, columns=columns, show="headings")
        
        # Set column headings
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        
        # Bind selection event
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(formats_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Download Button
        download_frame = ttk.Frame(root, padding="10")
        download_frame.pack(fill=tk.X)
        
        self.download_btn = ttk.Button(download_frame, text="Download", command=self.download_video, state=tk.DISABLED)
        self.download_btn.pack(side=tk.LEFT)
        
        # Progress bar
        self.progress = ttk.Progressbar(download_frame, mode='determinate', length=300)
        self.progress.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        
        self.status_label = ttk.Label(download_frame, text="")
        self.status_label.pack(side=tk.LEFT)
        
        self.formats = []

    def fetch_formats(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL")
            return
        
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.formats = []
        ydl_opts = {
            'quiet': True,
            'no_warnings': True
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                self.formats = info.get('formats', [])
                
                for f in self.formats:
                    filesize = f.get('filesize', 'N/A')
                    if filesize != 'N/A' and filesize is not None:
                        filesize = f"{filesize / 1024 / 1024:.1f}MB"
                    
                    self.tree.insert("", tk.END, values=(
                        f.get('format_id', 'N/A'),
                        f.get('ext', 'N/A'),
                        f.get('resolution', 'N/A'),
                        filesize,
                        f.get('format_note', '')
                    ))
        
        except Exception as e:
            messagebox.showerror("Error", str(e))
            
    def download_video(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a format")
            return
        
        format_id = str(self.tree.item(selection[0])['values'][0])  # Convert to string
        url = self.url_entry.get().strip()
        
        def download():
            try:
                ydl_opts = {
                    'format': format_id,
                    'outtmpl': '%(title)s.%(ext)s',
                    'progress_hooks': [self.progress_hook],
                    'retries': 10,  # Number of times to retry
                    'fragment_retries': 10,  # Number of times to retry a fragment
                    'continuedl': True,  # Force resume of partially downloaded files
                    'socket_timeout': 30,  # Timeout for network operations
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                messagebox.showinfo("Success", "Download completed!")
                self.status_label.configure(text="")
                self.progress['value'] = 0
                
            except Exception as e:
                messagebox.showerror("Error", str(e))
            
            finally:
                self.download_btn.configure(state=tk.NORMAL)
                self.url_entry.configure(state=tk.NORMAL)
        
        self.download_btn.configure(state=tk.DISABLED)
        self.url_entry.configure(state=tk.DISABLED)
        Thread(target=download, daemon=True).start()

    def on_select(self, event):
        selection = self.tree.selection()
        if selection:
            self.download_btn.configure(state=tk.NORMAL)
        else:
            self.download_btn.configure(state=tk.DISABLED)

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    percentage = (downloaded / total) * 100
                    self.progress['value'] = percentage
                    self.status_label.configure(text=f"{percentage:.1f}%")
            except:
                pass

if __name__ == '__main__':
    root = tk.Tk()
    app = VideoDownloaderGUI(root)
    root.mainloop()
