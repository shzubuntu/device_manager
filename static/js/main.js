import 'bootstrap';

class FileManager {
  constructor(deviceId) {
    this.deviceId = deviceId;
    this.remotePath = '/';
    this.localPath = '/home/songhz';
    this.init();
  }

  async init() {
    await this.loadLocalFiles();
    await this.loadRemoteFiles();
    this.setupEventListeners();
  }

  async loadLocalFiles(path = this.localPath) {
    try {
      const response = await fetch(`/file-manager/local-files/?path=${encodeURIComponent(path)}`);
      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }

      this.localPath = data.current_path;
      this.renderLocalFileList(data.files);
    } catch (error) {
      console.error('Failed to load local files:', error);
      alert('Failed to load local files: ' + error.message);
    }
  }

  renderLocalFileList(files) {
    const fileList = document.getElementById('local-files');
    fileList.innerHTML = '';

    files.forEach(file => {
      const item = this.createFileItem(file, 'local');
      fileList.appendChild(item);
    });

    // Update path display
    document.getElementById('local-path').textContent = this.localPath;
  }

  async loadRemoteFiles(path = this.remotePath) {
    try {
      const response = await fetch(`/file-manager/remote-files/${this.deviceId}/?path=${encodeURIComponent(path)}`);
      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error);
      }

      this.remotePath = data.current_path;
      this.renderRemoteFileList(data.files);
    } catch (error) {
      console.error('Failed to load remote files:', error);
      alert('Failed to load remote files: ' + error.message);
    }
  }

  createFileItem(file, type) {
    const item = document.createElement('div');
    item.className = 'file-item';
    item.textContent = file.name;

    if (file.is_dir) {
      item.classList.add('directory');
      item.addEventListener('click', () => {
        const currentPath = type === 'local' ? this.localPath : this.remotePath;
        const newPath = file.parent ? 
          currentPath.split('/').slice(0, -1).join('/') || '/' :
          `${currentPath}/${file.name}`;
        
        if (type === 'local') {
          this.loadLocalFiles(newPath);
        } else {
          this.loadRemoteFiles(newPath);
        }
      });
    }

    return item;
  }

  renderRemoteFileList(files) {
    const fileList = document.getElementById('remote-file-list');
    fileList.innerHTML = '';

    files.forEach(file => {
      const item = this.createFileItem(file, 'remote');
      fileList.appendChild(item);
    });

    // Update path display
    document.getElementById('remote-path').textContent = this.remotePath;
  }

  setupEventListeners() {
    document.getElementById('upload-btn').addEventListener('click', () => this.handleFileUpload());
  }

  async handleFileUpload() {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    
    fileInput.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('remote_path', this.remotePath);

        const response = await fetch(`/file-manager/upload/${this.deviceId}/`, {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          throw new Error('Upload failed');
        }

        await this.loadRemoteFiles();
        alert('File uploaded successfully');
      } catch (error) {
        console.error('Upload failed:', error);
        alert('Upload failed: ' + error.message);
      }
    };

    fileInput.click();
  }
}

// Initialize file manager when page loads
document.addEventListener('DOMContentLoaded', () => {
  const urlParams = new URLSearchParams(window.location.search);
  const deviceId = urlParams.get('device_id');
  
  if (deviceId) {
    console.log('Initializing file manager for device:', deviceId);
    const fileManager = new FileManager(deviceId);
    
    // 调试远程文件加载
    fileManager.loadRemoteFiles().then(() => {
      console.log('Remote files loaded successfully');
    }).catch(error => {
      console.error('Failed to load remote files:', error);
      alert('无法加载远程文件，请检查设备连接状态');
    });
  } else {
    console.error('Device ID not found in URL');
    alert('未找到设备ID，请从设备列表页面重新进入');
  }
});
