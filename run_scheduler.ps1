# PowerShell script to run the scheduler
# Save this as run_scheduler.ps1

# Navigate to the application directory
Set-Location "C:\Users\Ivermectin\Music\Tanush\Try 3"

# Activate the virtual environment (if using one)
# Uncomment the following line if you have a virtual environment
# & .\venv\Scripts\Activate.ps1

# Run the scheduler
python scheduler.py

# Log completion
Write-Output "Scheduler completed at $(Get-Date)"
