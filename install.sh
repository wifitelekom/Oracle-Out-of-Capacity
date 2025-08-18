#!/bin/bash

#############################################
# OCI OCC Fix Bot - Automated Installation Script
# This script sets up the complete environment
#############################################

echo "======================================"
echo "OCI OCC Fix Bot - Installation Script"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check Python version
print_status "Checking Python version..."
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
        print_status "Python $PYTHON_VERSION found"
    else
        print_error "Python 3.8+ required. Found: Python $PYTHON_VERSION"
        exit 1
    fi
else
    print_error "Python3 not found. Please install Python 3.8+"
    exit 1
fi

# Check if pip is installed
print_status "Checking pip..."
if ! command -v pip3 &>/dev/null; then
    print_warning "pip3 not found. Installing pip..."
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    python3 get-pip.py
    rm get-pip.py
fi

# Create virtual environment
print_status "Creating virtual environment..."
if [ -d "venv" ]; then
    print_warning "Virtual environment already exists. Skipping..."
else
    python3 -m venv venv
    print_status "Virtual environment created"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install requirements
print_status "Installing requirements..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    print_status "All requirements installed successfully"
else
    print_error "Failed to install some requirements"
    exit 1
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs
mkdir -p backup

# Check for configuration file
if [ -f "configuration.ini" ]; then
    print_status "Configuration file found"
else
    print_warning "Configuration file not found!"
    
    # Create sample configuration
    if [ -f "configuration.ini.sample" ]; then
        print_status "Copying sample configuration..."
        cp configuration.ini.sample configuration.ini
        print_warning "Please edit configuration.ini with your OCI credentials"
    else
        print_error "No configuration.ini or configuration.ini.sample found"
    fi
fi

# Check for OCI PEM key file
print_status "Checking for OCI PEM key file..."
if [ -f "configuration.ini" ]; then
    KEY_FILE=$(grep "key_file" configuration.ini | cut -d'=' -f2 | xargs)
    if [ -f "$KEY_FILE" ]; then
        print_status "OCI PEM key file found: $KEY_FILE"
    else
        print_warning "OCI PEM key file not found at: $KEY_FILE"
        print_warning "Please ensure your PEM key file exists at the specified location"
    fi
fi

# Create systemd service file (optional)
print_status "Creating systemd service file..."
cat > oci-bot.service << 'EOF'
[Unit]
Description=OCI OCC Fix Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
Environment="PATH=$PWD/venv/bin"
ExecStart=$PWD/venv/bin/python $PWD/oci-bot-with-web.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

print_status "Systemd service file created: oci-bot.service"
print_warning "To install as service, run:"
echo "  sudo cp oci-bot.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable oci-bot"
echo "  sudo systemctl start oci-bot"

# Create start script
print_status "Creating start script..."
cat > start.sh << 'EOF'
#!/bin/bash
source venv/bin/activate
python3 oci-bot-with-web.py
EOF
chmod +x start.sh

# Create stop script
cat > stop.sh << 'EOF'
#!/bin/bash
pkill -f "oci-bot-with-web.py"
echo "Bot stopped"
EOF
chmod +x stop.sh

# Create status script
cat > status.sh << 'EOF'
#!/bin/bash
if pgrep -f "oci-bot-with-web.py" > /dev/null; then
    echo "Bot is running"
    echo "PID: $(pgrep -f 'oci-bot-with-web.py')"
else
    echo "Bot is not running"
fi
EOF
chmod +x status.sh

echo ""
echo "======================================"
print_status "Installation completed successfully!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Edit configuration.ini with your OCI credentials"
echo "2. Ensure your OCI PEM key file is in place"
echo "3. Run the bot with: ./start.sh"
echo "4. Access web dashboard at: http://localhost:5000"
echo ""
echo "Useful commands:"
echo "  ./start.sh  - Start the bot"
echo "  ./stop.sh   - Stop the bot"
echo "  ./status.sh - Check bot status"
echo ""
print_warning "Don't forget to configure your firewall if accessing remotely!"
echo ""
