@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo  script-to-storyboard - Windows installer
echo ==================================================
echo Usage:
echo   install.bat              install dependencies only
echo   install.bat model       install dependencies AND download the SD 1.5 weights (~4.3 GB)
echo.

rem ------------------------------------------------ 1. find Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found on PATH.
    echo Install Python 3.10 or newer from https://python.org and tick "Add to PATH".
    exit /b 1
)

rem ------------------------------------------------ 2. virtual environment
if not exist ".venv" (
    echo Creating virtual environment .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Could not activate .venv. Run manually: .venv\Scripts\activate
    exit /b 1
)

rem ------------------------------------------------ 3. dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Package installation failed.
    echo If torch failed on an NVIDIA GPU, install the CUDA build instead:
    echo   pip install torch --index-url https://download.pytorch.org/whl/cu124
    exit /b 1
)

rem ------------------------------------------------ 4. optional model download
if /i "%~1"=="model" call :download_model
if errorlevel 1 exit /b 1

rem ------------------------------------------------ 5. verify
echo.
echo Checking the environment ...
python app.py --check

echo.
echo Setup complete.
echo   Run the app:            run.bat
echo   Shot list only:         run.bat --dry-run sample_script.txt
echo   Use the local model:    run.bat --model-dir models\sd1.5
exit /b 0

:download_model
echo Downloading stable-diffusion-v1-5 into models\sd1.5 ...
python -c "from huggingface_hub import snapshot_download; snapshot_download('stable-diffusion-v1-5/stable-diffusion-v1-5', local_dir='models/sd1.5', allow_patterns=['model_index.json','unet/config.json','unet/diffusion_pytorch_model.safetensors','vae/config.json','vae/diffusion_pytorch_model.safetensors','text_encoder/config.json','text_encoder/model.safetensors','tokenizer/*','scheduler/*','feature_extractor/*'])"
if errorlevel 1 (
    echo [ERROR] Model download failed. Check your internet connection or run it by hand with: hf download ...
    exit /b 1
)
exit /b 0
