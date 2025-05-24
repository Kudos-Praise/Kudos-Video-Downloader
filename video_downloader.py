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
    ydl_opts = {
        'format': format_id,
        'outtmpl': '%(title)s.%(ext)s',
        'retries': 10,  # Number of times to retry
        'fragment_retries': 10,  # Number of times to retry a fragment
        'continuedl': True,  # Force resume of partially downloaded files
        'socket_timeout': 30,  # Timeout for network operations
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"\nError during download: {str(e)}")
        print("Try downloading in a different format or check your internet connection.")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python video_downloader.py [URL]")
        sys.exit(1)
    
    url = sys.argv[1]
    if list_formats(url):
        format_id = input("\nEnter the Format ID you want to download (or press Enter for best quality): ").strip()
        if not format_id:
            format_id = 'best'
        else:
            format_id = str(format_id)  # Ensure format_id is a string
        download_video(url, format_id)
