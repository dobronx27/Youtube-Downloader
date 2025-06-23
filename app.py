from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import tempfile
import threading
import time
from urllib.parse import urlparse

app = Flask(__name__)

# Configuration
DOWNLOAD_FOLDER = tempfile.mkdtemp()
app.config['DOWNLOAD_FOLDER'] = DOWNLOAD_FOLDER

# Store download progress
download_progress = {}

def download_video(url, quality, download_id):
    """Download video with progress tracking"""
    try:
        download_progress[download_id] = {'status': 'downloading', 'progress': 0, 'filename': ''}
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                if 'total_bytes' in d and d['total_bytes']:
                    percent = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    download_progress[download_id]['progress'] = round(percent, 1)
                elif '_percent_str' in d:
                    percent_str = d['_percent_str'].replace('%', '')
                    try:
                        download_progress[download_id]['progress'] = float(percent_str)
                    except:
                        pass
            elif d['status'] == 'finished':
                download_progress[download_id]['status'] = 'completed'
                download_progress[download_id]['progress'] = 100
                download_progress[download_id]['filename'] = os.path.basename(d['filename'])
        
        # Configure yt-dlp options
        if quality == 'best':
            format_selector = 'best[ext=mp4]'
        elif quality == 'worst':
            format_selector = 'worst[ext=mp4]'
        else:
            format_selector = f'best[height<={quality}][ext=mp4]'
        
        ydl_opts = {
            'format': format_selector,
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'progress_hooks': [progress_hook],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
    except Exception as e:
        download_progress[download_id]['status'] = 'error'
        download_progress[download_id]['error'] = str(e)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_video_info', methods=['POST'])
def get_video_info():
    """Get video information"""
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Get available formats
            formats = []
            seen_heights = set()
            
            for f in info.get('formats', []):
                if f.get('ext') == 'mp4' and f.get('height'):
                    height = f['height']
                    if height not in seen_heights:
                        formats.append({
                            'height': height,
                            'quality': f"{height}p"
                        })
                        seen_heights.add(height)
            
            # Sort by quality (highest first)
            formats.sort(key=lambda x: x['height'], reverse=True)
            
            return jsonify({
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', 'Unknown'),
                'formats': formats
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download', methods=['POST'])
def download():
    """Start download process"""
    try:
        data = request.json
        url = data.get('url')
        quality = data.get('quality', 'best')
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        # Generate unique download ID
        download_id = str(int(time.time() * 1000))
        
        # Start download in background thread
        thread = threading.Thread(target=download_video, args=(url, quality, download_id))
        thread.daemon = True
        thread.start()
        
        return jsonify({'download_id': download_id})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/progress/<download_id>')
def get_progress(download_id):
    """Get download progress"""
    progress = download_progress.get(download_id, {'status': 'not_found'})
    return jsonify(progress)

@app.route('/download_file/<download_id>')
def download_file(download_id):
    """Download completed file"""
    progress = download_progress.get(download_id)
    if not progress or progress.get('status') != 'completed':
        return jsonify({'error': 'File not ready'}), 404
    
    filename = progress.get('filename')
    if not filename:
        return jsonify({'error': 'File not found'}), 404
    
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(filepath, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    # Create templates directory and HTML file
    os.makedirs('templates', exist_ok=True)
    
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube MP4 Downloader</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 50%, #0f0f0f 100%);
            color: #ffffff;
            min-height: 100vh;
            overflow-x: hidden;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            position: relative;
        }

        .header {
            text-align: center;
            margin-bottom: 40px;
            position: relative;
        }

        .header h1 {
            font-size: 3rem;
            font-weight: 700;
            background: linear-gradient(45deg, #ff6b35, #ff8c42, #ff6b35);
            background-size: 200% 200%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: gradient-shift 3s ease-in-out infinite;
            text-shadow: 0 0 30px rgba(255, 107, 53, 0.3);
        }

        @keyframes gradient-shift {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
        }

        .card {
            background: rgba(20, 20, 20, 0.9);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 107, 53, 0.2);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            position: relative;
            overflow: hidden;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 107, 53, 0.1), transparent);
            animation: shimmer 3s infinite;
        }

        @keyframes shimmer {
            0% { left: -100%; }
            100% { left: 100%; }
        }

        .input-group {
            position: relative;
            margin-bottom: 20px;
        }

        .input-group label {
            display: block;
            margin-bottom: 8px;
            color: #ff6b35;
            font-weight: 600;
        }

        .input-field {
            width: 100%;
            padding: 15px 20px;
            background: rgba(10, 10, 10, 0.8);
            border: 2px solid rgba(255, 107, 53, 0.3);
            border-radius: 12px;
            color: #ffffff;
            font-size: 16px;
            transition: all 0.3s ease;
        }

        .input-field:focus {
            outline: none;
            border-color: #ff6b35;
            box-shadow: 0 0 20px rgba(255, 107, 53, 0.3);
        }

        .btn {
            background: linear-gradient(45deg, #ff6b35, #ff8c42);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(255, 107, 53, 0.4);
        }

        .btn:active {
            transform: translateY(0);
        }

        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }

        .video-info {
            display: none;
            background: rgba(30, 30, 30, 0.9);
            border-radius: 15px;
            padding: 25px;
            margin: 20px 0;
            border-left: 4px solid #ff6b35;
        }

        .video-thumbnail {
            width: 100%;
            max-width: 300px;
            border-radius: 10px;
            margin-bottom: 15px;
        }

        .quality-selector {
            margin: 20px 0;
        }

        .quality-options {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .quality-option {
            background: rgba(255, 107, 53, 0.1);
            border: 2px solid rgba(255, 107, 53, 0.3);
            color: #ffffff;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .quality-option:hover, .quality-option.selected {
            background: #ff6b35;
            border-color: #ff6b35;
            transform: scale(1.05);
        }

        .progress-container {
            display: none;
            margin: 20px 0;
        }

        .progress-bar {
            width: 100%;
            height: 10px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 5px;
            overflow: hidden;
            margin-bottom: 10px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #ff6b35, #ff8c42);
            width: 0%;
            transition: width 0.3s ease;
            border-radius: 5px;
        }

        .progress-text {
            text-align: center;
            color: #ff6b35;
            font-weight: 600;
        }

        .error {
            background: rgba(220, 53, 69, 0.2);
            border: 1px solid rgba(220, 53, 69, 0.5);
            color: #ff6b6b;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }

        .success {
            background: rgba(40, 167, 69, 0.2);
            border: 1px solid rgba(40, 167, 69, 0.5);
            color: #4caf50;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }

        .floating-particles {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: -1;
        }

        .particle {
            position: absolute;
            width: 4px;
            height: 4px;
            background: #ff6b35;
            border-radius: 50%;
            opacity: 0.6;
            animation: float 6s infinite ease-in-out;
        }

        @keyframes float {
            0%, 100% { transform: translateY(0px) rotate(0deg); opacity: 0; }
            50% { transform: translateY(-100px) rotate(180deg); opacity: 1; }
        }

        .download-btn {
            display: none;
            margin-top: 20px;
        }

        @media (max-width: 768px) {
            .header h1 {
                font-size: 2rem;
            }
            
            .card {
                padding: 20px;
                margin: 10px;
            }
            
            .quality-options {
                justify-content: center;
            }
        }
    </style>
</head>
<body>
    <div class="floating-particles"></div>
    
    <div class="container">
        <div class="header">
            <h1>YouTube MP4 Downloader</h1>
        </div>

        <div class="card">
            <div class="input-group">
                <label for="youtube-url">YouTube URL</label>
                <input type="text" id="youtube-url" class="input-field" placeholder="Paste YouTube URL here...">
            </div>
            
            <button id="get-info-btn" class="btn">Get Video Info</button>
            
            <div id="error-message" class="error" style="display: none;"></div>
            
            <div id="video-info" class="video-info">
                <img id="video-thumbnail" class="video-thumbnail" alt="Video Thumbnail">
                <h3 id="video-title"></h3>
                <p><strong>Uploader:</strong> <span id="video-uploader"></span></p>
                <p><strong>Duration:</strong> <span id="video-duration"></span></p>
                
                <div class="quality-selector">
                    <label>Select Quality:</label>
                    <div id="quality-options" class="quality-options"></div>
                </div>
                
                <button id="download-btn" class="btn download-btn">Start Download</button>
                
                <div id="progress-container" class="progress-container">
                    <div class="progress-bar">
                        <div id="progress-fill" class="progress-fill"></div>
                    </div>
                    <div id="progress-text" class="progress-text">0%</div>
                </div>
                
                <div id="success-message" class="success" style="display: none;"></div>
            </div>
        </div>
    </div>

    <script>
        let currentDownloadId = null;
        let selectedQuality = 'best';

        // Create floating particles
        function createParticles() {
            const container = document.querySelector('.floating-particles');
            const particleCount = 50;

            for (let i = 0; i < particleCount; i++) {
                const particle = document.createElement('div');
                particle.className = 'particle';
                particle.style.left = Math.random() * 100 + '%';
                particle.style.animationDelay = Math.random() * 6 + 's';
                particle.style.animationDuration = (Math.random() * 3 + 3) + 's';
                container.appendChild(particle);
            }
        }

        createParticles();

        document.getElementById('get-info-btn').addEventListener('click', async function() {
            const url = document.getElementById('youtube-url').value.trim();
            const errorDiv = document.getElementById('error-message');
            const videoInfo = document.getElementById('video-info');
            
            if (!url) {
                showError('Please enter a YouTube URL');
                return;
            }

            this.disabled = true;
            this.textContent = 'Loading...';
            errorDiv.style.display = 'none';
            videoInfo.style.display = 'none';

            try {
                const response = await fetch('/get_video_info', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ url: url })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to get video info');
                }

                displayVideoInfo(data);
                videoInfo.style.display = 'block';

            } catch (error) {
                showError(error.message);
            } finally {
                this.disabled = false;
                this.textContent = 'Get Video Info';
            }
        });

        function displayVideoInfo(info) {
            document.getElementById('video-thumbnail').src = info.thumbnail;
            document.getElementById('video-title').textContent = info.title;
            document.getElementById('video-uploader').textContent = info.uploader;
            document.getElementById('video-duration').textContent = formatDuration(info.duration);

            const qualityOptions = document.getElementById('quality-options');
            qualityOptions.innerHTML = '';

            // Add quality options
            const qualities = [{ quality: 'best', height: 'Best' }, ...info.formats, { quality: 'worst', height: 'Worst' }];
            
            qualities.forEach((format, index) => {
                const option = document.createElement('div');
                option.className = 'quality-option';
                option.textContent = typeof format.height === 'string' ? format.height : format.quality;
                option.dataset.quality = format.quality || format.height;
                
                if (index === 0) {
                    option.classList.add('selected');
                    selectedQuality = option.dataset.quality;
                }

                option.addEventListener('click', function() {
                    document.querySelectorAll('.quality-option').forEach(opt => opt.classList.remove('selected'));
                    this.classList.add('selected');
                    selectedQuality = this.dataset.quality;
                });

                qualityOptions.appendChild(option);
            });

            document.getElementById('download-btn').style.display = 'block';
        }

        document.getElementById('download-btn').addEventListener('click', async function() {
            const url = document.getElementById('youtube-url').value.trim();
            const progressContainer = document.getElementById('progress-container');
            const successMessage = document.getElementById('success-message');

            this.disabled = true;
            this.textContent = 'Starting Download...';
            progressContainer.style.display = 'block';
            successMessage.style.display = 'none';

            try {
                const response = await fetch('/download', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ 
                        url: url, 
                        quality: selectedQuality 
                    })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to start download');
                }

                currentDownloadId = data.download_id;
                trackProgress();

            } catch (error) {
                showError(error.message);
                this.disabled = false;
                this.textContent = 'Start Download';
                progressContainer.style.display = 'none';
            }
        });

        async function trackProgress() {
            if (!currentDownloadId) return;

            try {
                const response = await fetch(`/progress/${currentDownloadId}`);
                const progress = await response.json();

                const progressFill = document.getElementById('progress-fill');
                const progressText = document.getElementById('progress-text');

                if (progress.status === 'downloading') {
                    progressFill.style.width = progress.progress + '%';
                    progressText.textContent = progress.progress + '%';
                    setTimeout(trackProgress, 1000);
                } else if (progress.status === 'completed') {
                    progressFill.style.width = '100%';
                    progressText.textContent = '100%';
                    showSuccess(`Download completed! <a href="/download_file/${currentDownloadId}" style="color: #4caf50; text-decoration: underline;">Click here to download</a>`);
                    document.getElementById('download-btn').disabled = false;
                    document.getElementById('download-btn').textContent = 'Start Download';
                } else if (progress.status === 'error') {
                    showError(progress.error || 'Download failed');
                    document.getElementById('download-btn').disabled = false;
                    document.getElementById('download-btn').textContent = 'Start Download';
                    document.getElementById('progress-container').style.display = 'none';
                } else {
                    setTimeout(trackProgress, 1000);
                }
            } catch (error) {
                showError('Failed to track progress');
                document.getElementById('download-btn').disabled = false;
                document.getElementById('download-btn').textContent = 'Start Download';
            }
        }

        function formatDuration(seconds) {
            if (!seconds) return 'Unknown';
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;
            
            if (hours > 0) {
                return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            } else {
                return `${minutes}:${secs.toString().padStart(2, '0')}`;
            }
        }

        function showError(message) {
            const errorDiv = document.getElementById('error-message');
            errorDiv.innerHTML = message;
            errorDiv.style.display = 'block';
        }

        function showSuccess(message) {
            const successDiv = document.getElementById('success-message');
            successDiv.innerHTML = message;
            successDiv.style.display = 'block';
        }
    </script>
</body>
</html>'''

    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("YouTube MP4 Downloader Web App")
    print("==============================")
    print("Starting server...")
    print("Open your browser and go to: http://localhost:5000")
    print("\nRequired dependencies:")
    print("pip install flask yt-dlp")
    print("\nPress Ctrl+C to stop the server")
    
    # For local network access, use your local IP
    # Find your IP with: ipconfig (Windows) or ifconfig (Mac/Linux)
    app.run(debug=True, host='0.0.0.0', port=5000)