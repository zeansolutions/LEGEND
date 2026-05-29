const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let pythonProcess = null;

// Determine if we are in development mode
const isDev = !app.isPackaged;

function startPythonAPI() {
    const pythonPath = '/home/zean/.gemini/antigravity/brain/7befb322-761a-4f1a-9b53-75eee7896ad7/scratch/venv/bin/python3';
    const apiScript = path.join(__dirname, '../api.py');
    
    console.log(`🚀 Launching Python API backend at ${apiScript}...`);
    
    pythonProcess = spawn(pythonPath, [apiScript], {
        stdio: 'inherit',
        env: { ...process.env, PYTHONUNBUFFERED: '1' }
    });
    
    pythonProcess.on('error', (err) => {
        console.error('❌ Failed to start Python API process:', err);
    });
    
    pythonProcess.on('close', (code) => {
        console.log(`ℹ️ Python process exited with code ${code}`);
    });
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1280,
        height: 800,
        minWidth: 1000,
        minHeight: 700,
        fullscreen: true, // Start in true immersive full screen mode
        frame: true, // Let's keep system controls for reliability, but build a beautiful responsive custom inner layout
        backgroundColor: '#070913',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        }
    });

    // Hide standard menu bar
    mainWindow.setMenuBarVisibility(false);

    // Open the window maximized automatically
    mainWindow.maximize();

    mainWindow.loadFile(path.join(__dirname, 'dist/index.html'));

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

app.whenReady().then(() => {
    startPythonAPI();
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    // Terminate Python API process
    if (pythonProcess) {
        console.log('Stopping Python API process...');
        pythonProcess.kill('SIGTERM');
        pythonProcess = null;
    }
    
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('will-quit', () => {
    if (pythonProcess) {
        pythonProcess.kill('SIGTERM');
    }
});
