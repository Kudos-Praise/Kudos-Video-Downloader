import sys
import yt_dlp

def list_formats(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            print("\nAvailable formats:")
            print("Format ID\tExtension\tResolution\tFilesize\t\tNote")
            print("-" * 80)
            
            for f in formats:
                filesize = f.get('filesize', 'N/A')
                if filesize != 'N/A' and filesize is not None:
                    filesize = f"{filesize / 1024 / 1024:.1f}MB"
                print(f"{f.get('format_id', 'N/A')}\t\t{f.get('ext', 'N/A')}\t\t{f.get('resolution', 'N/A')}\t\t{filesize}\t\t{f.get('format_note', '')}")
            
            return True
        except Exception as e:
            print(f"Error: {str(e)}")
            return False

def download_video(url, format_id='best'):
    def progress_hook(d):
        if d['status'] == 'downloading':
            try:
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0)
                
                if speed:
                    speed = speed / 1024  # Convert to KB/s
                    speed_str = f"{speed:.1f} KB/s"
                else:
                    speed_str = "N/A"
                
                if eta:
                    eta_str = f"{eta//60}:{eta%60:02d}"
                else:
                    eta_str = "N/A"
                
                if total:
                    percent = downloaded / total * 100
                    print(f"\rProgress: {percent:.1f}% | Speed: {speed_str} | ETA: {eta_str}", end="")
            except:
                pass
        elif d['status'] == 'finished':
            print("\nDownload completed!")

    ydl_opts = {
        'format': format_id,
        'outtmpl': '%(title)s_%(id)s.%(ext)s',  # Add video ID to filename to avoid conflicts
        'retries': 10,  # Number of times to retry
        'fragment_retries': 10,  # Number of times to retry a fragment
        'continuedl': True,  # Force resume of partially downloaded files
        'socket_timeout': 30,  # Timeout for network operations
        'progress_hooks': [progress_hook],
        'windowsfilenames': True,  # Ensure Windows-compatible filenames
        'ignoreerrors': True  # Continue on download errors
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"\nError during download: {str(e)}")
        print("Try downloading in a different format or check your internet connection.")

def download_multiple_videos(urls, format_id='best'):
    total_videos = len(urls)
    successful = 0
    failed = 0
    
    # Show formats only for the first video
    print(f"\nGetting available formats from the first video...")
    if not list_formats(urls[0]):
        print("Failed to get formats. Using best quality.")
    
    for index, url in enumerate(urls, 1):
        try:
            print(f"\nProcessing video {index} of {total_videos}")
            print(f"URL: {url}")
            download_video(url, format_id)
            successful += 1
        except Exception as e:
            print(f"\nFailed to download video {index}: {str(e)}")
            failed += 1
        print("-" * 80)
    
    # Print summary
    print(f"\nDownload Summary:")
    print(f"Total videos: {total_videos}")
    print(f"Successfully downloaded: {successful}")
    print(f"Failed: {failed}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python video_downloader.py [URL1] [URL2] ...")
        sys.exit(1)
    
    urls = sys.argv[1:]  # Get all URLs from command line arguments
    format_id = input("\nEnter the Format ID you want to download (or press Enter for best quality): ").strip()
    if not format_id:
        format_id = 'best'
    else:
        format_id = str(format_id)  # Ensure format_id is a string
    
    download_multiple_videos(urls, format_id)
