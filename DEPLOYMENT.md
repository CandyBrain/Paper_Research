# Paper_Research 배포 가이드

이 문서는 Paper_Research (Streamlit 기반 논문 검색/분석 앱)를 서버에 배포하는 방법을 설명합니다.

---

## 목차

1. [사전 준비사항](#사전-준비사항)
2. [AWS 배포](#1-aws-배포)
3. [라즈베리파이 / 데비안 PC 서버 배포](#2-라즈베리파이--데비안-pc-서버-배포)

---

## 사전 준비사항

### 필수 환경변수 (.env 파일)

```env
ANTHROPIC_API_KEY=your_anthropic_api_key
SCOPUS_API_KEY=your_scopus_api_key        # 선택
CORE_API_KEY=your_core_api_key            # 선택
UNPAYWALL_EMAIL=your_email@example.com    # 선택
PAPERS_DIR=papers
MAX_RESULTS_PER_DB=10
```

### Python 버전

- **Python 3.10 이상** 권장 (Streamlit 및 pydantic v2 호환)

---

## 1. AWS 배포

### 방법 A: EC2 인스턴스 (가장 직관적)

#### Step 1. EC2 인스턴스 생성

1. AWS 콘솔 > EC2 > "인스턴스 시작"
2. 추천 설정:
   - **AMI**: Ubuntu 22.04 LTS 또는 Amazon Linux 2023
   - **인스턴스 타입**: `t3.small` (2 vCPU, 2GB RAM) 이상 권장
     - 동시 접속자가 많으면 `t3.medium` (4GB RAM) 이상
   - **스토리지**: 20GB 이상 (PDF 저장 공간 포함)
3. **보안 그룹** 설정:
   - SSH: 포트 22 (내 IP만 허용)
   - HTTP: 포트 80 (0.0.0.0/0)
   - HTTPS: 포트 443 (0.0.0.0/0)
   - Custom TCP: 포트 8501 (Streamlit 기본 포트, 테스트용)

#### Step 2. 서버 초기 설정

```bash
# SSH 접속
ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>

# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# Python 및 필수 패키지 설치
sudo apt install -y python3 python3-pip python3-venv git nginx

# 프로젝트 클론
git clone https://github.com/candybrain/paper_research.git
cd paper_research

# 가상 환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

#### Step 3. 환경변수 설정

```bash
# .env 파일 생성
cat > .env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-xxxxx
SCOPUS_API_KEY=xxxxx
CORE_API_KEY=xxxxx
UNPAYWALL_EMAIL=your@email.com
PAPERS_DIR=papers
EOF
```

#### Step 4. systemd 서비스 등록 (자동 시작/재시작)

```bash
sudo tee /etc/systemd/system/paper-research.service << 'EOF'
[Unit]
Description=Paper Research Streamlit App
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/paper_research
Environment="PATH=/home/ubuntu/paper_research/venv/bin:/usr/bin"
ExecStart=/home/ubuntu/paper_research/venv/bin/streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable paper-research
sudo systemctl start paper-research
```

#### Step 5. Nginx 리버스 프록시 설정 (포트 80/443으로 접속)

```bash
sudo tee /etc/nginx/sites-available/paper-research << 'EOF'
server {
    listen 80;
    server_name your-domain.com;  # 또는 EC2 퍼블릭 IP

    client_max_body_size 100M;  # PDF 업로드 크기 제한

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # Streamlit WebSocket 지원 (필수)
    location /_stcore/stream {
        proxy_pass http://127.0.0.1:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/paper-research /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```

#### Step 6. HTTPS 설정 (Let's Encrypt, 도메인이 있는 경우)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
# 자동 갱신은 certbot이 알아서 설정함
```

#### 접속 확인

- `http://<EC2-PUBLIC-IP>` (Nginx 설정 후)
- `http://<EC2-PUBLIC-IP>:8501` (직접 접속, 테스트)

---

### 방법 B: AWS Lightsail (더 간단하고 저렴)

EC2보다 간단하고 **월 $3.50~$10**로 고정 요금.

1. AWS Lightsail > "인스턴스 생성"
2. OS: Ubuntu 22.04
3. 플랜: $5/월 (1GB RAM, 1 vCPU) 이상
4. 이후 설정은 EC2와 동일 (Step 2~6)

---

### 방법 C: AWS App Runner + Docker (관리형 서비스)

자동 스케일링이 필요한 경우.

#### Dockerfile 작성 (프로젝트 루트에 생성)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port=8501", \
    "--server.address=0.0.0.0", \
    "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
```

#### 배포 순서

1. Docker 이미지 빌드 후 **Amazon ECR**에 push
2. **AWS App Runner** 서비스 생성 시 ECR 이미지 선택
3. 환경변수에 API 키 설정
4. 포트: 8501
5. 자동으로 HTTPS, 도메인, 오토스케일링 제공

---

### AWS 비용 예상

| 구성 | 월 예상 비용 |
|------|-------------|
| EC2 t3.small (온디맨드) | ~$15-20 |
| EC2 t3.small (예약 1년) | ~$8-10 |
| Lightsail 1GB | $5 |
| Lightsail 2GB | $10 |
| App Runner (저사용량) | ~$5-15 |

> 참고: Anthropic API 호출 비용은 별도입니다.

---

## 2. 라즈베리파이 / 데비안 PC 서버 배포

### 지원 여부

| 환경 | 지원 | 비고 |
|------|------|------|
| 라즈베리파이 4/5 (4GB+) | O | ARM64, Raspberry Pi OS (Debian 기반) |
| 라즈베리파이 3 (1GB) | △ | 메모리 부족 가능, swap 필수 |
| 데비안/우분투 PC | O | x86_64, 가장 안정적 |

### Step 1. 시스템 준비

```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# Python 3.10+ 설치 확인
python3 --version
# 3.10 미만이면:
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa  # Ubuntu인 경우
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 기타 필수 패키지
sudo apt install -y git nginx curl
```

### 라즈베리파이 전용: Swap 설정 (RAM 4GB 미만인 경우)

```bash
# 기존 swap 확인
free -h

# swap 파일 생성 (2GB)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 적용
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Step 2. 프로젝트 설치

```bash
# 프로젝트 클론
cd /home/$USER
git clone https://github.com/candybrain/paper_research.git
cd paper_research

# 가상 환경 생성
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
# 라즈베리파이에서 시간이 좀 걸릴 수 있음 (5~15분)
```

### Step 3. 환경변수 설정

```bash
cat > .env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-xxxxx
SCOPUS_API_KEY=xxxxx
CORE_API_KEY=xxxxx
UNPAYWALL_EMAIL=your@email.com
PAPERS_DIR=papers
EOF
```

### Step 4. 테스트 실행

```bash
source venv/bin/activate
streamlit run app.py --server.headless=true --server.address=0.0.0.0
# 브라우저에서 http://<서버IP>:8501 접속 확인
```

### Step 5. systemd 서비스 등록

```bash
sudo tee /etc/systemd/system/paper-research.service << EOF
[Unit]
Description=Paper Research Streamlit App
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/paper_research
Environment="PATH=/home/$USER/paper_research/venv/bin:/usr/bin"
ExecStart=/home/$USER/paper_research/venv/bin/streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable paper-research
sudo systemctl start paper-research

# 상태 확인
sudo systemctl status paper-research
```

### Step 6. Nginx 리버스 프록시

```bash
sudo tee /etc/nginx/sites-available/paper-research << 'EOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    location /_stcore/stream {
        proxy_pass http://127.0.0.1:8501/_stcore/stream;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/paper-research /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```

### Step 7. 외부 접속 설정

#### 방법 A: 공유기 포트 포워딩 (집에서 서비스)

1. 공유기 관리 페이지 접속 (보통 `192.168.0.1` 또는 `192.168.1.1`)
2. 포트 포워딩 설정:
   - 외부 포트 80 -> 내부 IP:80 (서버의 내부 IP)
   - 외부 포트 443 -> 내부 IP:443 (HTTPS 사용 시)
3. 서버 내부 IP 고정:
   ```bash
   # /etc/dhcpcd.conf (라즈베리파이) 또는 netplan (Ubuntu)
   # 라즈베리파이 예시:
   sudo tee -a /etc/dhcpcd.conf << 'EOF'
   interface eth0
   static ip_address=192.168.0.100/24
   static routers=192.168.0.1
   static domain_name_servers=8.8.8.8 8.8.4.4
   EOF
   sudo systemctl restart dhcpcd
   ```

#### 방법 B: DDNS (동적 IP 환경)

집 인터넷의 공인 IP가 바뀌는 경우:

1. 무료 DDNS 서비스 가입 (Duck DNS, No-IP 등)
2. DDNS 클라이언트 설치:
   ```bash
   # Duck DNS 예시
   mkdir -p ~/duckdns
   cat > ~/duckdns/duck.sh << 'EOF'
   #!/bin/bash
   echo url="https://www.duckdns.org/update?domains=YOUR_DOMAIN&token=YOUR_TOKEN&ip=" | curl -k -o ~/duckdns/duck.log -K -
   EOF
   chmod +x ~/duckdns/duck.sh

   # 5분마다 IP 갱신
   (crontab -l 2>/dev/null; echo "*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1") | crontab -
   ```

#### 방법 C: Cloudflare Tunnel (포트 포워딩 불필요, 추천)

포트 포워딩 없이도 외부 접속 가능:

```bash
# cloudflared 설치 (라즈베리파이 ARM64)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# x86_64 PC의 경우
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# 터널 생성 (Cloudflare 계정 필요, 무료)
cloudflared tunnel login
cloudflared tunnel create paper-research
cloudflared tunnel route dns paper-research paper.your-domain.com

# 터널 설정
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: <TUNNEL_ID>
credentials-file: /home/$USER/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: paper.your-domain.com
    service: http://localhost:8501
  - service: http_status:404
EOF

# systemd로 터널 자동 실행
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

### Step 8. HTTPS 설정 (도메인이 있는 경우)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.duckdns.org
```

---

## 관리 명령어 모음

```bash
# 서비스 상태 확인
sudo systemctl status paper-research

# 서비스 재시작
sudo systemctl restart paper-research

# 로그 확인
sudo journalctl -u paper-research -f

# 코드 업데이트 후 재시작
cd /home/$USER/paper_research
git pull origin master
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart paper-research
```

---

## 주의사항

1. **API 키 보안**: `.env` 파일에 API 키를 저장하고, `.gitignore`에 이미 포함되어 있으므로 Git에 커밋되지 않습니다.
2. **tkinter 관련**: `app.py`의 폴더 선택 기능(`pick_folder`)은 GUI 환경이 필요합니다. 서버 배포 시 이 기능은 동작하지 않지만, 앱의 핵심 기능(논문 검색/분석)에는 영향 없습니다.
3. **방화벽**: `ufw`를 사용하는 경우 포트를 열어주세요:
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw allow 22/tcp
   sudo ufw enable
   ```
4. **라즈베리파이 성능**: Anthropic API 호출 자체는 외부 서버에서 처리되므로 라즈베리파이에서도 응답 속도는 양호합니다. 다만 동시 접속자가 많으면 Streamlit 자체가 느려질 수 있습니다.
5. **PDF 저장 공간**: 라즈베리파이는 SD 카드 용량이 제한적이므로, 외장 USB/SSD를 마운트하여 `PAPERS_DIR`을 해당 경로로 설정하는 것을 권장합니다.
