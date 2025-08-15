// 初始化终端
function initTerminal(wsUrl, protocol) {
    const terminal = new Terminal({
        cursorBlink: true,
        scrollback: 1000,
        tabStopWidth: 8,
        fontSize: 14
    });

    // 设置协议相关参数
    const protocolParams = {
        protocol: protocol,
        host: document.getElementById('host').value,
        port: document.getElementById('port').value,
        username: document.getElementById('username').value,
        password: document.getElementById('password').value,
        deviceType: document.getElementById('deviceType').value
    };

    const fitAddon = new window.FitAddon();
    terminal.loadAddon(fitAddon);

    terminal.open(document.getElementById('terminal'));
    fitAddon.fit();

    const ws = new WebSocket(wsUrl);
    ws.onopen = () => {
        // 发送连接参数
        ws.send(JSON.stringify({
            type: 'connect',
            ...protocolParams
        }));
        terminal.write('\r\n*** Connected to device terminal ***\r\n');
    };

    ws.onmessage = (event) => {
        terminal.write(event.data);
    };

    ws.onclose = () => {
        terminal.write('\r\n*** Connection closed ***\r\n');
    };

    terminal.onData(data => {
        ws.send(data);
    });

    window.addEventListener('resize', () => {
        fitAddon.fit();
    });

    return ws;
}

// 文件传输日志
let fileTransferLog = [];
const maxLogEntries = 100;

// 添加传输日志
function addTransferLog(type, filename, status, message = '') {
    const logEntry = {
        timestamp: new Date().toISOString(),
        type: type,
        filename: filename,
        status: status,
        message: message
    };
    
    fileTransferLog.push(logEntry);
    
    // 保持日志长度
    if (fileTransferLog.length > maxLogEntries) {
        fileTransferLog.shift();
    }
    
    // 更新日志显示
    updateTransferLogDisplay();
}

// 更新日志显示
function updateTransferLogDisplay() {
    const logElement = document.getElementById('transfer-log');
    if (!logElement) return;
    
    logElement.innerHTML = fileTransferLog
        .map(entry => `
            <div class="log-entry">
                <span class="timestamp">${new Date(entry.timestamp).toLocaleString()}</span>
                <span class="type">${entry.type}</span>
                <span class="filename">${entry.filename}</span>
                <span class="status ${entry.status}">${entry.status}</span>
                ${entry.message ? `<span class="message">${entry.message}</span>` : ''}
            </div>
        `)
        .join('');
}

// 计算文件校验和
async function calculateChecksum(content) {
    const encoder = new TextEncoder();
    const data = encoder.encode(content);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

// 文件上传
async function uploadFile() {
    const fileInput = document.getElementById('uploadFile');
    const remotePath = document.getElementById('remotePath').value;
    const progressBar = document.getElementById('uploadProgress');
    const maxFileSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = ['text/plain', 'application/json', 'text/x-python'];
    const maxRetries = 3;
    let retryCount = 0;

    // 添加传输日志
    addTransferLog('upload', fileInput.files[0]?.name || 'unknown', 'pending');
    
    if (!fileInput.files.length || !remotePath) {
        alert('请选择文件并输入远程路径');
        return;
    }

    const file = fileInput.files[0];
    
    // 检查文件类型
    if (!allowedTypes.includes(file.type)) {
        alert('不支持的文件类型');
        return;
    }

    // 检查文件大小
    if (file.size > maxFileSize) {
        alert('文件大小超过10MB限制');
        return;
    }

    // 显示进度条
    if (progressBar) {
        progressBar.style.display = 'block';
        progressBar.value = 0;
    }

    const reader = new FileReader();
    
    reader.onloadstart = () => {
        if (progressBar) {
            progressBar.value = 0;
        }
    };

    reader.onprogress = (e) => {
        if (e.lengthComputable && progressBar) {
            const percent = (e.loaded / e.total) * 100;
            progressBar.value = percent;
        }
    };

    reader.onload = async function(e) {
        try {
            const content = e.target.result;
            const checksum = await calculateChecksum(content);
            
            currentWs.send(JSON.stringify({
                type: 'upload',
                filename: file.name,
                remote_path: remotePath,
                content: content,
                size: file.size,
                checksum: checksum
            }));

            // 监听上传结果
            const originalOnMessage = currentWs.onmessage;
            currentWs.onmessage = async (event) => {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'upload_result') {
                        if (data.success) {
                            addTransferLog('upload', file.name, 'success', '文件上传成功');
                        } else {
                            addTransferLog('upload', file.name, 'failed', data.message);
                            if (retryCount < maxRetries) {
                                retryCount++;
                                addTransferLog('upload', file.name, 'retrying', `第 ${retryCount} 次重试`);
                                setTimeout(() => reader.readAsText(file), 1000);
                            } else {
                                addTransferLog('upload', file.name, 'failed', '超过最大重试次数');
                            }
                        }
                        return;
                    }
                    
                    // 处理其他消息
                    originalOnMessage(event);
                } catch (err) {
                    console.error('上传结果处理失败:', err);
                    addTransferLog('upload', file.name, 'failed', '上传结果处理失败');
                }
            };

            if (progressBar) {
                progressBar.value = 100;
                setTimeout(() => {
                    progressBar.style.display = 'none';
                }, 2000);
            }
        } catch (err) {
            console.error('文件上传失败:', err);
            alert('文件上传失败');
            if (progressBar) {
                progressBar.style.display = 'none';
            }
        }
    };

    reader.onerror = () => {
        alert('文件读取失败');
        if (progressBar) {
            progressBar.style.display = 'none';
        }
    };
    
    reader.readAsText(file);
}

// 文件下载
async function downloadFile() {
    const remotePath = document.getElementById('downloadPath').value;
    const progressBar = document.getElementById('downloadProgress');
    const maxFileSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = ['text/plain', 'application/json', 'text/x-python'];
    
    if (!remotePath) {
        alert('请输入远程文件路径');
        return;
    }

    // 显示进度条
    if (progressBar) {
        progressBar.style.display = 'block';
        progressBar.value = 0;
    }

    // 发送下载请求
    currentWs.send(JSON.stringify({
        type: 'download',
        filename: remotePath.split('/').pop(),
        remote_path: remotePath
    }));

    // 监听下载进度
    const originalOnMessage = currentWs.onmessage;
    currentWs.onmessage = async (event) => {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'download_progress') {
                if (progressBar) {
                    progressBar.value = data.progress;
                }
                return;
            }

            if (data.type === 'download_complete') {
                // 检查文件类型
                if (!allowedTypes.includes(data.file_type)) {
                    addTransferLog('download', data.filename, 'failed', '不支持的文件类型');
                    alert('不支持的文件类型');
                    return;
                }

                // 检查文件大小
                if (data.file_size > maxFileSize) {
                    addTransferLog('download', data.filename, 'failed', '文件大小超过10MB限制');
                    alert('文件大小超过10MB限制');
                    return;
                }

                // 验证校验和
                const localChecksum = await calculateChecksum(data.content);
                if (localChecksum !== data.checksum) {
                    addTransferLog('download', data.filename, 'failed', '文件校验失败');
                    alert('文件校验失败，请重试');
                    return;
                }

                // 创建下载链接
                const blob = new Blob([data.content], { type: data.file_type });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = data.filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);

                // 记录成功日志
                addTransferLog('download', data.filename, 'success', '文件下载成功');

                // 隐藏进度条
                if (progressBar) {
                    progressBar.value = 100;
                    setTimeout(() => {
                        progressBar.style.display = 'none';
                    }, 2000);
                }
                return;
            }

            // 处理其他消息
            originalOnMessage(event);
        } catch (err) {
            console.error('文件下载失败:', err);
            alert('文件下载失败');
            if (progressBar) {
                progressBar.style.display = 'none';
            }
        }
    };

    // 处理下载错误
    const originalOnError = currentWs.onerror;
    currentWs.onerror = (error) => {
        console.error('文件下载错误:', error);
        alert('文件下载错误');
        if (progressBar) {
            progressBar.style.display = 'none';
        }
        originalOnError(error);
    };
}

// 打开文件传输窗口
function openFileTransfer() {
    // 获取terminal元素
    const terminalElement = document.getElementById('terminal');
    
    // 确保设备ID存在
    if (!terminalElement || !terminalElement.dataset.deviceId) {
        alert('请先连接设备');
        return;
    }
    
    const deviceId = terminalElement.dataset.deviceId;
    
    // 构建URL并验证
    const url = `/file-manager/remote-files/${deviceId}/?path=/`;
    console.log('Opening file manager:', url);
    
    // 使用GET方法直接打开新窗口
    window.open(url, '_blank');
}


// 绑定文件传输按钮点击事件
const fileTransferBtn = document.getElementById('fileTransferBtn');
if (fileTransferBtn) {
    fileTransferBtn.addEventListener('click', openFileTransfer);
}
