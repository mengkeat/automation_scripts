class AVConfigManager {
    constructor() {
        this.selectedFiles = new Set();
        this.currentFiles = [];
        this.pendingMergeContent = null;
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // Root directory setup
        document.getElementById('setRootBtn').addEventListener('click', () => this.setRootDirectory());
        document.getElementById('rootPath').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.setRootDirectory();
        });

        // File operations
        document.getElementById('scanBtn').addEventListener('click', () => this.scanFiles());
        document.getElementById('selectAllBtn').addEventListener('click', () => this.selectAllFiles());
        document.getElementById('deselectAllBtn').addEventListener('click', () => this.deselectAllFiles());

        // Preview and merge
        document.getElementById('previewBtn').addEventListener('click', () => this.previewSelected());
        document.getElementById('mergeBtn').addEventListener('click', () => this.mergeFiles());

        // Master config
        document.getElementById('showMasterBtn').addEventListener('click', () => this.showMasterConfig());

        // Modal events
        document.querySelector('.close').addEventListener('click', () => this.closeModal());
        document.getElementById('proceedAnyway').addEventListener('click', () => this.proceedWithMerge());
        document.getElementById('cancelMerge').addEventListener('click', () => this.closeModal());

        // Close modal when clicking outside
        window.addEventListener('click', (e) => {
            const modal = document.getElementById('conflictModal');
            if (e.target === modal) {
                this.closeModal();
            }
        });
    }

    async setRootDirectory() {
        const rootPath = document.getElementById('rootPath').value.trim();
        if (!rootPath) {
            this.showStatus('Please enter a root directory path', 'error');
            return;
        }

        this.showLoading(true);
        try {
            const response = await fetch('/api/set_root', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ root_path: rootPath })
            });

            const result = await response.json();
            if (result.success) {
                this.showStatus(result.message, 'success');
                this.enableButtons(['scanBtn']);
            } else {
                this.showStatus(result.message, 'error');
            }
        } catch (error) {
            this.showStatus('Error setting root directory: ' + error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async scanFiles() {
        this.showLoading(true);
        try {
            const response = await fetch('/api/scan_files');
            const result = await response.json();
            this.currentFiles = result.files;
            this.displayFiles(result.files);
            this.enableButtons(['selectAllBtn', 'deselectAllBtn']);
        } catch (error) {
            this.showStatus('Error scanning files: ' + error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    displayFiles(files) {
        const fileList = document.getElementById('fileList');
        if (files.length === 0) {
            fileList.innerHTML = '<p style="padding: 20px; text-align: center; color: #666;">No YAML files found in params/nodes directory</p>';
            return;
        }

        fileList.innerHTML = files.map(file => `
            <div class="file-item">
                <input type="checkbox" id="file-${file.path}" value="${file.path}" 
                       onchange="configManager.toggleFileSelection('${file.path}')">
                <div class="file-info">
                    <div class="file-name">${file.name}</div>
                    <div class="file-path">${file.relative_path}</div>
                </div>
                <div class="file-size">${this.formatFileSize(file.size)}</div>
            </div>
        `).join('');
    }

    toggleFileSelection(filePath) {
        const checkbox = document.getElementById(`file-${filePath}`);
        if (checkbox.checked) {
            this.selectedFiles.add(filePath);
        } else {
            this.selectedFiles.delete(filePath);
        }
        
        this.updateSelectionButtons();
    }

    selectAllFiles() {
        this.currentFiles.forEach(file => {
            this.selectedFiles.add(file.path);
            document.getElementById(`file-${file.path}`).checked = true;
        });
        this.updateSelectionButtons();
    }

    deselectAllFiles() {
        this.selectedFiles.clear();
        this.currentFiles.forEach(file => {
            document.getElementById(`file-${file.path}`).checked = false;
        });
        this.updateSelectionButtons();
    }

    updateSelectionButtons() {
        const hasSelection = this.selectedFiles.size > 0;
        this.enableButtons(hasSelection ? ['previewBtn'] : [], ['previewBtn']);
    }

    async previewSelected() {
        if (this.selectedFiles.size === 0) {
            this.showStatus('Please select at least one file', 'error');
            return;
        }

        this.showLoading(true);
        try {
            const response = await fetch('/api/merge_files', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ file_paths: Array.from(this.selectedFiles) })
            });

            const result = await response.json();
            if (result.error) {
                this.showStatus(result.error, 'error');
                return;
            }

            this.pendingMergeContent = result.content;
            const previewArea = document.getElementById('previewArea');
            
            let previewText = '# Merged Configuration Preview\n\n';
            previewText += `Selected files: ${this.selectedFiles.size}\n`;
            previewText += `Conflicts detected: ${result.conflicts.length}\n\n`;
            
            if (result.conflicts.length > 0) {
                previewText += '## CONFLICTS:\n';
                result.conflicts.forEach(conflict => {
                    previewText += `⚠️  ${conflict}\n`;
                });
                previewText += '\n';
            }
            
            previewText += '## Merged Content:\n';
            previewText += this.yamlToString(result.content);

            previewArea.textContent = previewText;
            this.enableButtons(['mergeBtn']);

        } catch (error) {
            this.showStatus('Error previewing files: ' + error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async mergeFiles() {
        if (!this.pendingMergeContent) {
            this.showStatus('Please preview files first', 'error');
            return;
        }

        // Check for conflicts first
        this.showLoading(true);
        try {
            const response = await fetch('/api/merge_files', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ file_paths: Array.from(this.selectedFiles) })
            });

            const result = await response.json();
            
            if (result.conflicts && result.conflicts.length > 0) {
                this.showConflictModal(result.conflicts);
                this.showLoading(false);
                return;
            }

            await this.saveMergedConfig();
        } catch (error) {
            this.showStatus('Error checking conflicts: ' + error.message, 'error');
            this.showLoading(false);
        }
    }

    showConflictModal(conflicts) {
        const modal = document.getElementById('conflictModal');
        const conflictList = document.getElementById('conflictList');
        
        conflictList.innerHTML = conflicts.map(conflict => `<li>${conflict}</li>`).join('');
        modal.style.display = 'block';
    }

    closeModal() {
        document.getElementById('conflictModal').style.display = 'none';
    }

    async proceedWithMerge() {
        this.closeModal();
        this.showLoading(true);
        await this.saveMergedConfig();
    }

    async saveMergedConfig() {
        try {
            const response = await fetch('/api/save_merged', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ content: this.pendingMergeContent })
            });

            const result = await response.json();
            if (result.success) {
                this.showStatus(result.message, 'success');
                this.selectedFiles.clear();
                this.deselectAllFiles();
                this.pendingMergeContent = null;
                document.getElementById('previewArea').textContent = '';
                this.enableButtons([], ['previewBtn', 'mergeBtn']);
            } else {
                this.showStatus(result.message, 'error');
            }
        } catch (error) {
            this.showStatus('Error saving configuration: ' + error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async showMasterConfig() {
        this.showLoading(true);
        try {
            const response = await fetch('/api/master_config');
            const result = await response.json();
            
            const configDisplay = document.getElementById('masterConfig');
            if (Object.keys(result.config).length === 0) {
                configDisplay.textContent = 'Master configuration is empty';
            } else {
                configDisplay.textContent = this.yamlToString(result.config);
            }
        } catch (error) {
            this.showStatus('Error loading master config: ' + error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    yamlToString(obj, indent = 0) {
        if (obj === null || obj === undefined) return 'null';
        if (typeof obj === 'string') return obj;
        if (typeof obj === 'number' || typeof obj === 'boolean') return String(obj);
        
        if (Array.isArray(obj)) {
            return obj.map((item, index) => 
                '  '.repeat(indent) + `- ${this.yamlToString(item, indent + 1)}`
            ).join('\n');
        }
        
        if (typeof obj === 'object') {
            return Object.entries(obj).map(([key, value]) => {
                const spaces = '  '.repeat(indent);
                if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                    return `${spaces}${key}:\n${this.yamlToString(value, indent + 1)}`;
                } else {
                    return `${spaces}${key}: ${this.yamlToString(value, indent + 1)}`;
                }
            }).join('\n');
        }
        
        return String(obj);
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    showStatus(message, type) {
        const statusElement = document.getElementById('rootStatus');
        statusElement.textContent = message;
        statusElement.className = `status-message ${type}`;
        
        // Auto-hide success messages after 5 seconds
        if (type === 'success') {
            setTimeout(() => {
                statusElement.style.display = 'none';
            }, 5000);
        }
    }

    enableButtons(enable = [], disable = []) {
        enable.forEach(id => {
            const button = document.getElementById(id);
            if (button) button.disabled = false;
        });
        
        disable.forEach(id => {
            const button = document.getElementById(id);
            if (button) button.disabled = true;
        });
    }

    showLoading(show) {
        const overlay = document.getElementById('loadingOverlay');
        overlay.style.display = show ? 'flex' : 'none';
    }
}

// Initialize the application
const configManager = new AVConfigManager();