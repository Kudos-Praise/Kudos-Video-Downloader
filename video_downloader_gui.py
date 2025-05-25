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
import threading

class DownloadProgress:
    def __init__(self, url, format_id, parent):
        self.url = url
        self.format_id = format_id
        self.progress = 0
        self.status = "Pending"
        self.speed = "0 KB/s"
        self.eta = "Unknown"
        self.lock = Lock()
        self.paused = False
        
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
        
        # Control buttons
        self.pause_btn = ttk.Button(self.frame, text="⏸", width=3, command=self.toggle_pause)
        self.pause_btn.pack(side=tk.LEFT, padx=2)
        
        self.remove_btn = ttk.Button(self.frame, text="✕", width=3, command=self.remove)
        self.remove_btn.pack(side=tk.LEFT, padx=2)

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_btn.configure(text="▶" if self.paused else "⏸")
        self.status = "Paused" if self.paused else "Downloading"
        self.status_label.configure(text=self.status)

    def remove(self):
        self.frame.destroy()
        if hasattr(self, 'parent'):
            self.parent.remove_download(self)

    def update(self, progress, status, speed=None, eta=None):
        with self.lock:
            if not self.paused:
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
        ttk.Button(btn_frame, text="Import Links", command=self.import_links).pack(fill=tk.X, pady=1)
        self.get_formats_button = btn_frame.winfo_children()[0] # Get the reference to the Get Formats button
        
        # Location frame - Compact
        loc_frame = ttk.Frame(main_frame)
        loc_frame.pack(fill=tk.X, pady=2)
        ttk.Label(loc_frame, text="Save to:").pack(side=tk.LEFT)
        self.location_entry = ttk.Entry(loc_frame)
        self.location_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.location_entry.insert(0, os.path.expanduser("~/Downloads"))
        ttk.Button(loc_frame, text="...", width=3, command=self.browse_location).pack(side=tk.LEFT)
        
        # Add queue control buttons
        queue_control_frame = ttk.Frame(main_frame)
        queue_control_frame.pack(fill=tk.X, pady=2)
        
        ttk.Button(queue_control_frame, text="Clear Queue", command=self.clear_queue).pack(side=tk.LEFT, padx=5)
        ttk.Button(queue_control_frame, text="Pause All", command=self.pause_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(queue_control_frame, text="Resume All", command=self.resume_all).pack(side=tk.LEFT, padx=5)
        
        # Queue status label
        self.queue_status = ttk.Label(queue_control_frame, text="Queue: 0 items")
        self.queue_status.pack(side=tk.RIGHT, padx=5)
        
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
        self.video_info = None
        self.thumbnail_loaded = False

    def show_preview_window(self, video_info):
        if self.preview_window:
            self.preview_window.destroy()
        
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("Video Preview")
        self.preview_window.geometry("400x500")
        
        # Create loading frame
        loading_frame = ttk.Frame(self.preview_window)
        loading_frame.pack(fill=tk.BOTH, expand=True)
        
        # Loading indicator
        ttk.Label(loading_frame, text="Loading video information...").pack(pady=20)
        progress = ttk.Progressbar(loading_frame, mode='indeterminate')
        progress.pack(fill=tk.X, padx=20)
        progress.start()
        
        # Start loading video info and thumbnail in parallel
        Thread(target=self.load_video_info, args=(video_info, loading_frame), daemon=True).start()
        Thread(target=self.load_thumbnail, args=(video_info['thumbnail'], loading_frame), daemon=True).start()

    def load_video_info(self, video_info, loading_frame):
        try:
            # Create format options
            format_options = []
            for f in self.formats:
                # Get format details
                format_note = f.get('format_note', '')
                ext = f.get('ext', '')
                resolution = f.get('resolution', '')
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')
                
                # Create a more detailed format string
                format_str = f"{format_note} - {ext} ({resolution})"
                if vcodec != 'none':
                    format_str += f" [Video: {vcodec}]"
                if acodec != 'none':
                    format_str += f" [Audio: {acodec}]"
                
                format_options.append((format_str, f['format_id']))
            
            # Update UI in main thread
            self.root.after(0, lambda: self.update_preview_info(video_info, format_options, loading_frame))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to load video info: {str(e)}"))

    def load_thumbnail(self, thumbnail_url, loading_frame):
        try:
            response = requests.get(thumbnail_url)
            img_data = Image.open(BytesIO(response.content))
            img_data = img_data.resize((360, 240), Image.Resampling.LANCZOS)
            self.preview_image = ImageTk.PhotoImage(img_data)
            
            # Update UI in main thread
            self.root.after(0, lambda: self.update_preview_thumbnail(loading_frame))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to load thumbnail: {str(e)}"))

    def update_preview_info(self, video_info, format_options, loading_frame):
        # Clear loading frame
        for widget in loading_frame.winfo_children():
            widget.destroy()
        
        # Preview image (if loaded)
        if self.preview_image:
            img_label = ttk.Label(loading_frame, image=self.preview_image)
            img_label.pack(pady=10)
        
        # Video info
        info_frame = ttk.Frame(loading_frame)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"Title: {video_info['title']}").pack(anchor='w')
        ttk.Label(info_frame, text=f"Duration: {video_info['duration']} seconds").pack(anchor='w')
        
        # Format selection
        format_frame = ttk.Frame(loading_frame)
        format_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(format_frame, text="Select Format:").pack(anchor='w')
        
        self.format_var = tk.StringVar()
        format_combo = ttk.Combobox(format_frame, textvariable=self.format_var, values=[f[0] for f in format_options])
        format_combo.pack(fill=tk.X, pady=5)
        
        # Download button
        ttk.Button(loading_frame, text="Add to Download Queue", 
                  command=lambda: self.add_to_queue(format_options[format_combo.current()][1] if format_combo.current() >= 0 else None)
                  ).pack(pady=10)

    def update_preview_thumbnail(self, loading_frame):
        if self.preview_image and not self.thumbnail_loaded:
            self.thumbnail_loaded = True
            # Find the first label in the frame and update its image
            for widget in loading_frame.winfo_children():
                if isinstance(widget, ttk.Label):
                    widget.configure(image=self.preview_image)
                    break

    def add_to_queue(self, format_id):
        if not format_id:
            messagebox.showwarning("Warning", "Please select a format")
            return
        
        # Get all URLs from the text area - this will now include all playlist items if detected
        urls_to_queue = [url.strip() for url in self.urls_text.get(1.0, tk.END).splitlines() if url.strip()]
        
        if not urls_to_queue:
            messagebox.showerror("Error", "No URLs to add to the queue.")
            return
        
        # Add all URLs to queue
        for url in urls_to_queue:
            # Only add if not already in active_downloads (prevents duplicates if add_to_queue is called multiple times)
            if url not in self.active_downloads:
                self.download_queue.put((url, format_id))
                progress = DownloadProgress(url, format_id, self.scrollable_frame)
                progress.parent = self  # Add reference to parent for removal
                self.active_downloads[url] = progress
            else:
                 print(f"Skipping {url} as it is already in the download list.") # Optional: provide feedback if skipping
        
        self.update_queue_status()
        self.preview_window.destroy()
        
        # Start download workers if not already running or if queue has items
        if not self.downloading or self.download_queue.qsize() > 0:
            self.start_download_workers()

    def start_download_workers(self):
        self.downloading = True
        
        def download_worker():
            # Workers continue as long as there are items in the queue or active downloads
            while not self.download_queue.empty() or any(d.status in ["Pending", "Downloading"] for d in self.active_downloads.values()):
                try:
                    # Use get_nowait() to avoid blocking if the queue is temporarily empty but downloads are still active
                    # Added a timeout to get_nowait to prevent excessive CPU usage in the loop condition check
                    url, format_id = self.download_queue.get_nowait()
                    
                    progress = self.active_downloads.get(url)
                    
                    # Check if download object exists, hasn't been removed, and is not paused
                    if progress is None or not progress.frame.winfo_exists():
                        # If frame doesn't exist, the item was likely removed via the GUI
                        self.download_queue.task_done()
                        continue

                    if progress.paused:
                         # If paused, put it back and check the queue again after a short delay
                         self.download_queue.put((url, format_id)) # Put item back
                         time.sleep(1) # Wait a bit before checking again
                         continue # Go to the next iteration to get another item
                         
                    progress.update(0, "Downloading")
                    
                    try:
                        self.download_single_video(url, format_id, progress)
                        if progress.frame.winfo_exists():
                            # Only update if the frame still exists (wasn't removed during download)
                            progress.update(100, "Completed")
                    except Exception as e:
                        print(f"Error downloading {url}: {e}") # Log the error
                        if progress.frame.winfo_exists():
                             # Only update if the frame still exists
                            progress.update(0, f"Failed: {str(e)}")
                            
                    self.download_queue.task_done()
                    self.update_queue_status()
                except Queue.Empty:
                    # If the queue is empty, but there are still active downloads, wait a bit
                    # This prevents the worker from exiting prematurely if downloads are slow
                    time.sleep(0.5) # Reduced sleep time slightly
                except Exception as e:
                    print(f"An unexpected error occurred in download worker: {e}")
                    time.sleep(0.5) # Prevent tight loop on unexpected errors
            
            # The worker thread will exit when the queue is empty AND there are no active downloads.
            self.downloading = False # Indicate that downloads are no longer active (though queue might still have items if workers exited due to errors)
            self.update_queue_status() # Final status update
            
        # Start worker threads if not enough are running
        # Ensure enough threads are running up to max_concurrent_downloads
        # Filter out threads that are alive and are our download workers
        active_worker_threads = [thread for thread in threading.enumerate() if thread.is_alive() and getattr(thread, 'name', None) == "download_worker_thread"]
        
        while len(active_worker_threads) < self.max_concurrent_downloads:
             thread = Thread(target=download_worker, daemon=True)
             thread.name = "download_worker_thread" # Assign a name for easy identification
             thread.start()
             active_worker_threads.append(thread) # Add the new thread to the list

    def download_single_video(self, url, format_id, progress):
        download_path = os.path.join(self.location_entry.get(), '%(title)s_%(id)s.%(ext)s')
        ydl_opts = {
            'format': format_id,
            'outtmpl': download_path,
            'progress_hooks': [lambda d: self.progress_hook(d, progress)],
            'retries': 3, # Further reduce retries to fail faster on restricted content
            'fragment_retries': 3, # Further reduce retries
            'continuedl': True,
            'socket_timeout': 10, # Further reduce timeout
            'windowsfilenames': True,
            'ignoreerrors': True, # Keep this to allow yt-dlp to handle some errors internally
            'no_overwrites': True,
            'extract_flat': False
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
            except Exception as e:
                # Re-raise the exception so the download_worker can catch and handle it
                raise e

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
        # Disable the button and show loading state
        self.get_formats_button.config(state=tk.DISABLED)
        original_text = self.get_formats_button.cget('text')
        self.get_formats_button.config(text="Loading...")

        urls = [url.strip() for url in self.urls_text.get(1.0, tk.END).splitlines() if url.strip()]
        if not urls:
            messagebox.showerror("Error", "Please enter at least one URL")
            self.get_formats_button.config(state=tk.NORMAL)
            self.get_formats_button.config(text=original_text)
            return

        # Use the first URL for initial processing to detect playlist or get single video info
        initial_url = urls[0]

        self.formats = []
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            # Use extract_flat initially to quickly check for playlist structure
            'extract_flat': True,
            'ignoreerrors': True, # Ignore errors during extraction/listing
            'no_abort_on_error': True # Do not abort the entire playlist process on error
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(initial_url, download=False)

                if info.get('_type') == 'playlist' and 'entries' in info:
                    # This is a playlist
                    if messagebox.askyesno("Playlist Detected",
                        f"This is a playlist with {len(info['entries'])} videos. Would you like to add all videos to the list?"):

                        # Clear the text area
                        self.urls_text.delete(1.0, tk.END)

                        # Add all playlist URLs to the text area
                        playlist_urls = []
                        for entry in info['entries']:
                            # Try to get the URL or construct it from the ID
                            video_url = entry.get('url') or (f"https://www.youtube.com/watch?v={entry.get('id')}" if entry.get('id') else None)
                            # Only add the URL if it's not None and doesn't indicate an error/empty entry
                            # We might get an entry with an error status if ignoreerrors is true, skip these.
                            if video_url and not entry.get('_type') == 'url_transparent' and not entry.get('url') == '' and not entry.get('title') == '[private]' and not entry.get('title') == '[deleted]': # Added checks for common problematic entry types/titles
                                playlist_urls.append(video_url)
                            elif entry.get('url') == '' or entry.get('title') in ['[private]', '[deleted]']:
                                print(f"Skipping problematic or restricted video in playlist: {entry.get('title', entry.get('id', 'Unknown'))}") # Provide feedback for skipped videos

                        if playlist_urls:
                            self.urls_text.insert(tk.END, '\n'.join(playlist_urls))

                            # Now, get formats for the first video in the populated text area for preview
                            # Need to re-read the text area as it now contains all playlist URLs
                            updated_urls = [url.strip() for url in self.urls_text.get(1.0, tk.END).splitlines() if url.strip()]
                            if updated_urls:
                                # Get detailed info for the first video for preview (ensure not extract_flat and no_abort_on_error=False for single video detail fetch)
                                single_video_ydl_opts = {
                                    'quiet': True,
                                    'no_warnings': True,
                                    'extract_flat': False,
                                    'ignoreerrors': False, # Do not ignore errors when getting detailed info for a single video
                                    'no_abort_on_error': False # Abort if getting info for the selected video fails
                                }
                                # Use a new YDL instance for the single video detailed info fetch
                                try:
                                    with yt_dlp.YoutubeDL(single_video_ydl_opts) as single_ydl:
                                         first_video_info = single_ydl.extract_info(updated_urls[0], download=False)
                                    self.formats = first_video_info.get('formats', [])

                                    # Show preview window for the first video
                                    self.show_preview_window({
                                        'title': first_video_info.get('title', 'Unknown'),
                                        'duration': first_video_info.get('duration', 0),
                                        'thumbnail': first_video_info.get('thumbnail', '')
                                    })
                                except Exception as single_video_e:
                                    messagebox.showwarning("Warning", f"Could not retrieve detailed information for the first video in the playlist: {str(single_video_e)}\nOther videos might still be added to the queue if you proceed.")
                                    # In case of failure to get info for the first video, self.formats will be empty,
                                    # but the user might still want to try adding the other videos with default options.
                                    # We can show a basic preview window or allow adding without format selection.
                                    # For now, let's re-enable the button and inform the user.
                                    self.get_formats_button.config(state=tk.NORMAL)
                                    self.get_formats_button.config(text=original_text)
                                    return # Exit after showing warning if first video info fetch fails

                        else:
                            messagebox.showwarning("Warning", "No valid videos could be extracted from the playlist.")

                    # If it was a playlist URL but user said no, or if no valid urls were extracted from playlist,
                    # the button should be re-enabled and the process stops here for this input.
                    self.get_formats_button.config(state=tk.NORMAL)
                    self.get_formats_button.config(text=original_text)
                    return # Exit the function after handling playlist confirmation

                else: # This handles single videos or types that are not playlists with entries
                    # Not a playlist with entries, proceed as with a single video
                    # We need detailed info now, ensure extract_flat is False and ignoreerrors/no_abort_on_error are default (False for single video info)
                    single_video_ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': False,
                        'ignoreerrors': False,
                        'no_abort_on_error': False
                    }
                    # Re-fetch info for detailed format list using a new YDL instance
                    with yt_dlp.YoutubeDL(single_video_ydl_opts) as single_ydl:
                         detailed_info = single_ydl.extract_info(initial_url, download=False)
                    self.formats = detailed_info.get('formats', [])

                    # Show preview window for the single video
                    self.show_preview_window({
                        'title': detailed_info.get('title', 'Unknown'),
                        'duration': detailed_info.get('duration', 0),
                        'thumbnail': detailed_info.get('thumbnail', '')
                    })

        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            # Re-enable the button if it wasn't already re-enabled by playlist handling or single video info fetch failure
            if self.get_formats_button.cget('state') == tk.DISABLED:
                 self.get_formats_button.config(state=tk.NORMAL)
                 self.get_formats_button.config(text=original_text)

    def browse_location(self):
        directory = filedialog.askdirectory(
            initialdir=self.location_entry.get(),
            title="Select Download Location"
        )
        if directory:
            self.location_entry.delete(0, tk.END)
            self.location_entry.insert(0, directory)

    def clear_queue(self):
        # Clear the download queue
        while not self.download_queue.empty():
            try:
                self.download_queue.get_nowait()
                self.download_queue.task_done()
            except:
                pass
        
        # Remove all download progress frames
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.active_downloads.clear()
        self.update_queue_status()

    def pause_all(self):
        for download in self.active_downloads.values():
            if not download.paused:
                download.toggle_pause()

    def resume_all(self):
        for download in self.active_downloads.values():
            if download.paused:
                download.toggle_pause()

    def remove_download(self, download):
        if download.url in self.active_downloads:
            del self.active_downloads[download.url]
            self.update_queue_status()

    def update_queue_status(self):
        active = len(self.active_downloads)
        queued = self.download_queue.qsize()
        self.queue_status.configure(text=f"Queue: {active} active, {queued} pending")

    def import_links(self):
        file_path = filedialog.askopenfilename(
            title="Select Links File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    links = file.readlines()
                
                # Filter out empty lines and strip whitespace
                valid_links = [link.strip() for link in links if link.strip()]
                
                if valid_links:
                    # Clear existing content
                    self.urls_text.delete(1.0, tk.END)
                    # Insert new links
                    self.urls_text.insert(tk.END, '\n'.join(valid_links))
                    messagebox.showinfo("Success", f"Imported {len(valid_links)} links successfully!")
                else:
                    messagebox.showwarning("Warning", "No valid links found in the file.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import links: {str(e)}")

if __name__ == '__main__':
    root = tk.Tk()
    app = VideoDownloaderGUI(root)
    root.mainloop()
