# Oracle-Out-of-Capacity
Oracle Resolving Out of Host Capacity error
# 🚀 OCI OCC Fix Bot - Deployment Guide

## 📋 Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- OCI account with configured credentials
- Linux/macOS/Windows with WSL2

## 🔧 Quick Installation

### Method 1: Automated Installation (Recommended)

```bash
# Clone or download the bot files
# Make installation script executable
chmod +x install.sh

# Run installation
./install.sh
```

### Method 2: Manual Installation

```bash
# 1. Create virtual environment
python3 -m venv venv

# 2. Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install requirements
pip install -r requirements.txt

# 4. Create necessary directories
mkdir -p logs backup

# 5. Configure the bot
cp configuration.ini.sample configuration.ini
nano configuration.ini  # Edit with your credentials
```

## 🐳 Docker Deployment

### Using Docker Compose (Easiest)

```bash
# 1. Build and start container
docker-compose up -d

# 2. View logs
docker-compose logs -f

# 3. Stop container
docker-compose down
```

### Using Docker directly

```bash
# 1. Build image
docker build -t oci-bot .

# 2. Run container
docker run -d \
  --name oci-bot \
  -p 5000:5000 \
  -v $(pwd)/configuration.ini:/app/configuration.ini:ro \
  -v $(pwd)/bullvar.pem:/app/bullvar.pem:ro \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  oci-bot

# 3. View logs
docker logs -f oci-bot
```

## 📁 File Structure

```
oci-occ-bot/
├── oci-bot-with-web.py       # Main bot script
├── configuration.ini          # Configuration file
├── requirements.txt           # Python dependencies
├── bullvar.pem               # OCI API key (keep secure!)
├── logs/                     # Log files directory
│   └── oci_occ.log
├── backup/                   # Backup directory
├── install.sh               # Installation script
├── start.sh                 # Start script
├── stop.sh                  # Stop script
├── status.sh                # Status check script
├── Dockerfile               # Docker configuration
└── docker-compose.yml       # Docker Compose configuration
```

## ⚙️ Configuration

### Essential Configuration (configuration.ini)

```ini
[DEFAULT]
user = ocid1.user.oc1..aaaaaaaa...
fingerprint = aa:bb:cc:dd:ee:ff...
key_file = /path/to/your/key.pem
tenancy = ocid1.tenancy.oc1..aaaaaaaa...
region = eu-frankfurt-1

[OCI]
compartment_id = ocid1.tenancy.oc1..aaaaaaaa...
subnet_id = ocid1.subnet.oc1..aaaaaaaa...
image_id = ocid1.image.oc1..aaaaaaaa...
availability_domains = ["AD-1", "AD-2", "AD-3"]

[Instance]
display_name = my-instance
ssh_keys = ssh-rsa AAAAB3NzaC1yc2E...
boot_volume_size = 50

[Machine]
type = ARM
shape = VM.Standard.A1.Flex
ocpus = 1
memory = 6

[Dashboard]
enabled = true
host = 0.0.0.0
port = 5000
username = admin
password = your-secure-password

[Telegram]
bot_token = 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
uid = 123456789
```

## 🖥️ Running the Bot

### Development Mode

```bash
# Activate virtual environment
source venv/bin/activate

# Run the bot
python3 oci-bot-with-web.py
```

### Production Mode

#### Option 1: Using start script
```bash
./start.sh
```

#### Option 2: Using systemd (Linux)

```bash
# Copy service file
sudo cp oci-bot.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start
sudo systemctl enable oci-bot

# Start the service
sudo systemctl start oci-bot

# Check status
sudo systemctl status oci-bot

# View logs
sudo journalctl -u oci-bot -f
```

#### Option 3: Using screen/tmux

```bash
# Using screen
screen -S oci-bot
./start.sh
# Detach: Ctrl+A, D

# Using tmux
tmux new -s oci-bot
./start.sh
# Detach: Ctrl+B, D
```

#### Option 4: Using nohup

```bash
nohup python3 oci-bot-with-web.py > output.log 2>&1 &
```

## 🌐 Web Dashboard Access

### Local Access
```
http://localhost:5000
```

### Remote Access
```
http://YOUR_SERVER_IP:5000
```

### Firewall Configuration

```bash
# Ubuntu/Debian
sudo ufw allow 5000/tcp

# CentOS/RHEL
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload

# AWS EC2 - Add to Security Group
# Port: 5000, Protocol: TCP, Source: 0.0.0.0/0
```

## 🔒 Security Best Practices

1. **Protect your PEM key**
   ```bash
   chmod 600 bullvar.pem
   ```

2. **Use strong passwords**
   - Change default dashboard password
   - Use complex passwords

3. **Restrict access**
   ```ini
   [Dashboard]
   host = 127.0.0.1  # Local only
   ```

4. **Use HTTPS (with nginx)**
   ```nginx
   server {
       listen 443 ssl;
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       
       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

5. **Environment variables for sensitive data**
   ```bash
   export OCI_USER_OCID=ocid1.user...
   export OCI_FINGERPRINT=aa:bb:cc...
   export TELEGRAM_BOT_TOKEN=123456789:ABC...
   ```

## 🔍 Monitoring

### Check bot status
```bash
./status.sh
```

### View logs
```bash
# Real-time logs
tail -f logs/oci_occ.log

# Last 100 lines
tail -n 100 logs/oci_occ.log

# Search for errors
grep ERROR logs/oci_occ.log
```

### Web Dashboard Metrics
- Total Attempts
- Success Rate
- Error Statistics
- Live Logs
- Current Status

## 🛠️ Troubleshooting

### Bot won't start
```bash
# Check Python version
python3 --version

# Check dependencies
pip list

# Check configuration
python3 -c "import configparser; c=configparser.ConfigParser(); c.read('configuration.ini'); print(c.sections())"
```

### Can't access dashboard
```bash
# Check if port is in use
netstat -tulpn | grep 5000

# Check firewall
sudo iptables -L | grep 5000
```

### OCI API errors
```bash
# Test OCI configuration
python3 -c "import oci; config = oci.config.from_file('./config'); oci.config.validate_config(config)"
```

## 📊 Performance Optimization

### Adjust retry intervals
```ini
[Retry]
min_interval = 3      # Faster retries
max_interval = 30     # Don't wait too long
initial_retry_interval = 5
backoff_factor = 1.5
```

### System resources
```bash
# Limit CPU usage
nice -n 10 python3 oci-bot-with-web.py

# Limit memory usage
systemd-run --uid=$USER --gid=$USER --scope -p MemoryLimit=500M python3 oci-bot-with-web.py
```

## 🔄 Updates

### Update bot code
```bash
# Backup current version
cp oci-bot-with-web.py oci-bot-with-web.py.backup

# Replace with new version
# Then restart the bot
./stop.sh && ./start.sh
```

### Update dependencies
```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

## 📝 Backup

### Backup configuration
```bash
cp configuration.ini backup/configuration.ini.$(date +%Y%m%d)
```

### Backup logs
```bash
tar -czf backup/logs_$(date +%Y%m%d).tar.gz logs/
```

## 🌍 Multi-Region Deployment

Run multiple instances for different regions:

```bash
# Frankfurt instance
python3 oci-bot-with-web.py --config config-frankfurt.ini --port 5001

# Amsterdam instance
python3 oci-bot-with-web.py --config config-amsterdam.ini --port 5002

# Zurich instance
python3 oci-bot-with-web.py --config config-zurich.ini --port 5003
```

## 📞 Support

- Check logs first: `logs/oci_occ.log`
- Web dashboard: `http://localhost:5000`
- Telegram notifications (if configured)

## 🎉 Success Indicators

- Dashboard shows "Running" status
- No errors in logs
- Attempts counter increasing
- Error statistics showing "OutOfHostCapacity"
- Telegram notifications working (if configured)

---

**Note:** Keep your OCI credentials and PEM key secure. Never commit them to version control!
