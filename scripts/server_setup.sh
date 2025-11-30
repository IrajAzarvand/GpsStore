#!/bin/bash

# اسکریپت راه‌اندازی سرور برای GpsStore
# این اسکریپت تمام مراحل نصب را به صورت خودکار انجام می‌دهد

set -e

# رنگ‌ها برای خروجی
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# توابع
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# بررسی دسترسی root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        log_error "لطفاً این اسکریپت را با sudo اجرا کنید"
        exit 1
    fi
}

# به‌روزرسانی سیستم
update_system() {
    log_step "به‌روزرسانی سیستم..."
    apt update
    apt upgrade -y
    apt install -y curl wget git vim ufw
    log_info "سیستم به‌روزرسانی شد"
}

# نصب Docker
install_docker() {
    log_step "نصب Docker..."
    
    # حذف نسخه‌های قدیمی
    apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # نصب dependencies
    apt install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # اضافه کردن GPG key
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # اضافه کردن repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # نصب Docker
    apt update
    apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # راه‌اندازی Docker
    systemctl enable docker
    systemctl start docker
    
    log_info "Docker نصب شد: $(docker --version)"
}

# تنظیم فایروال
setup_firewall() {
    log_step "تنظیم فایروال..."
    
    # فعال‌سازی UFW
    ufw --force enable
    
    # باز کردن پورت‌ها
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    log_info "فایروال تنظیم شد"
    ufw status
}

# بررسی نصب
verify_installation() {
    log_step "بررسی نصب..."
    
    if command -v docker &> /dev/null; then
        log_info "✓ Docker نصب شده است"
    else
        log_error "✗ Docker نصب نشده است"
        exit 1
    fi
    
    if docker compose version &> /dev/null; then
        log_info "✓ Docker Compose نصب شده است"
    else
        log_error "✗ Docker Compose نصب نشده است"
        exit 1
    fi
}

# پیام نهایی
final_message() {
    log_info "=========================================="
    log_info "راه‌اندازی سرور با موفقیت انجام شد!"
    log_info "=========================================="
    log_warn "نکته مهم:"
    log_warn "اگر کاربری غیر از root دارید، باید آن را به گروه docker اضافه کنید:"
    log_warn "sudo usermod -aG docker \$USER"
    log_warn "سپس از سرور خارج شوید و دوباره وارد شوید."
    log_info ""
    log_info "مراحل بعدی:"
    log_info "1. پروژه را به سرور آپلود کنید"
    log_info "2. فایل .env را تنظیم کنید"
    log_info "3. docker compose up -d --build را اجرا کنید"
    log_info "4. migration‌ها را اجرا کنید"
}

# اجرای اصلی
main() {
    log_info "شروع راه‌اندازی سرور برای GpsStore..."
    log_info ""
    
    check_root
    update_system
    install_docker
    setup_firewall
    verify_installation
    final_message
}

# اجرا
main "$@"

