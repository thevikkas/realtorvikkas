# Realtor Vikkas v1.0 — Production Operations Guide

**Updated:** 2026-09-11  
**Version:** 1.0.0  
**Status:** 🟢 PRODUCTION READY

---

## 📊 PRODUCTION MONITORING

### **Real-Time Monitoring Commands**

#### Monitor Application Status
```bash
# Check service is running
systemctl status realtorvikkas

# Watch service logs in real-time
journalctl -u realtorvikkas -f

# Watch application error logs
tail -f /var/www/realtorvikkas/error.log

# Watch performance logs
tail -f /var/www/realtorvikkas/performance.log
```

#### Monitor Server Resources
```bash
# Interactive resource monitor
htop

# Check CPU and memory usage
top

# Disk usage
df -h
du -sh /var/www/realtorvikkas

# Network connections to app
netstat -an | grep 8000
```

#### Monitor Nginx
```bash
# Check Nginx status
systemctl status nginx

# View Nginx access logs
tail -f /var/log/nginx/access.log

# View Nginx error logs
tail -f /var/log/nginx/error.log

# Check active connections
netstat -an | grep ESTABLISHED | wc -l
```

### **Performance Metrics**

#### Check Query Performance
```bash
# See slow queries (>100ms)
grep "SLOW_QUERY" /var/www/realtorvikkas/performance.log | tail -20

# Count slow queries in last hour
grep "SLOW_QUERY" /var/www/realtorvikkas/performance.log | tail -100 | wc -l

# See cache hit rate
grep -c "Cache hit" /var/www/realtorvikkas/performance.log
```

#### Database Health
```bash
# Check database integrity
sqlite3 /var/www/realtorvikkas/realtorvikkas.db "PRAGMA integrity_check;"

# Get database size
ls -lh /var/www/realtorvikkas/realtorvikkas.db

# Check number of records per table
sqlite3 /var/www/realtorvikkas/realtorvikkas.db "
SELECT name, COUNT(*) as count
FROM sqlite_master
WHERE type='table'
;"
```

#### Security Events
```bash
# View security events
grep "SECURITY_EVENT" /var/www/realtorvikkas/error.log

# Check failed login attempts
grep "Failed login" /var/www/realtorvikkas/auth.log

# Check account lockouts
grep "locked out" /var/www/realtorvikkas/auth.log
```

---

## 🚨 TROUBLESHOOTING

### **Application Won't Start**

**Symptom:** Service fails to start or crashes immediately

**Diagnosis:**
```bash
# Check service status
sudo systemctl status realtorvikkas

# View error logs
sudo tail -50 /var/www/realtorvikkas/error.log

# Try running manually
cd /var/www/realtorvikkas
python3 app.py --port 8000
```

**Common Causes & Fixes:**

1. **Port Already in Use**
   ```bash
   # Find process using port 8000
   lsof -i :8000
   
   # Kill if necessary
   kill -9 <PID>
   
   # Restart service
   sudo systemctl restart realtorvikkas
   ```

2. **Database Locked**
   ```bash
   # Check for stuck connections
   sqlite3 /var/www/realtorvikkas/realtorvikkas.db "PRAGMA busy_timeout = 5000;"
   
   # Optimize database
   sqlite3 /var/www/realtorvikkas/realtorvikkas.db "VACUUM;"
   
   # Restart application
   sudo systemctl restart realtorvikkas
   ```

3. **Permission Issues**
   ```bash
   # Fix permissions
   sudo chown -R www-data:www-data /var/www/realtorvikkas
   sudo chmod -R 755 /var/www/realtorvikkas
   sudo chmod +x /var/www/realtorvikkas/app.py
   
   # Restart service
   sudo systemctl restart realtorvikkas
   ```

4. **Python Module Missing**
   ```bash
   # Check Python version
   python3 --version
   
   # The app uses stdlib only (no pip installs needed)
   # If error about missing module, reinstall Python
   sudo apt-get install --reinstall python3
   ```

---

### **Application Crashes**

**Symptom:** Application was running, now it's down

**Immediate Action:**
```bash
# Restart the service (auto-restart should trigger, but manual restart faster)
sudo systemctl restart realtorvikkas

# Verify it's running
sudo systemctl status realtorvikkas
```

**Investigation:**
```bash
# Check last error
sudo tail -100 /var/www/realtorvikkas/error.log

# Search for specific error patterns
grep -i "error\|exception\|traceback" /var/www/realtorvikkas/error.log | tail -20

# Check system logs
sudo journalctl -u realtorvikkas -n 50
```

---

### **Performance Degradation**

**Symptom:** Application is slow or unresponsive

**Diagnosis:**
```bash
# Check slow queries
grep "SLOW_QUERY" /var/www/realtorvikkas/performance.log | tail -20

# Check server load
uptime
top -b -n 1 | head -20

# Check database size
ls -lh /var/www/realtorvikkas/realtorvikkas.db
```

**Common Causes & Fixes:**

1. **Too Many Slow Queries**
   ```bash
   # Analyze queries that are taking >100ms
   grep "SLOW_QUERY" /var/www/realtorvikkas/performance.log | sort | uniq -c | sort -rn
   
   # Check if indexes exist
   sqlite3 /var/www/realtorvikkas/realtorvikkas.db ".schema" | grep INDEX
   ```

2. **Database Needs Optimization**
   ```bash
   # Run optimization manually
   sqlite3 /var/www/realtorvikkas/realtorvikkas.db << EOF
ANALYZE;
VACUUM;
EOF

   # Restart to clear query cache
   sudo systemctl restart realtorvikkas
   ```

3. **Cache Not Working**
   ```bash
   # Check if cache is hitting
   grep "Cache hit" /var/www/realtorvikkas/performance.log | wc -l
   
   # If cache misses high, may need to restart to warm cache
   # Cache is in-memory and resets on restart (TTL 3600s)
   ```

4. **High Memory Usage**
   ```bash
   # Check memory
   free -h
   
   # If over 80%, restart to clear cache
   sudo systemctl restart realtorvikkas
   
   # Check if running multiple instances
   ps aux | grep "python3.*app.py"
   ```

---

### **Database Issues**

**Symptom:** Database locked, queries timing out, or data corruption

**Diagnosis:**
```bash
# Check database integrity
sqlite3 /var/www/realtorvikkas/realtorvikkas.db "PRAGMA integrity_check;"

# Get database info
sqlite3 /var/www/realtorvikkas/realtorvikkas.db << EOF
PRAGMA page_count;
PRAGMA page_size;
PRAGMA freelist_count;
EOF

# Check for transactions
sqlite3 /var/www/realtorvikkas/realtorvikkas.db ".tables"
```

**Common Issues & Fixes:**

1. **Database Locked**
   ```bash
   # Kill any stuck connections (be careful!)
   # First, check who's connected
   lsof /var/www/realtorvikkas/realtorvikkas.db
   
   # Gracefully restart application
   sudo systemctl restart realtorvikkas
   
   # If still locked, force restart
   sudo systemctl kill -9 realtorvikkas
   sudo systemctl restart realtorvikkas
   ```

2. **Database Corrupted**
   ```bash
   # Backup corrupted database
   cp /var/www/realtorvikkas/realtorvikkas.db /var/www/realtorvikkas/backups/corrupted.db
   
   # Check corruption
   sqlite3 /var/www/realtorvikkas/realtorvikkas.db "PRAGMA integrity_check;"
   
   # Try to recover (dump and reload)
   sqlite3 /var/www/realtorvikkas/realtorvikkas.db ".dump" > /tmp/dump.sql
   
   # Restore from backup
   cp /var/www/realtorvikkas/backups/realtorvikkas.db.backup.* /var/www/realtorvikkas/realtorvikkas.db
   
   # Restart application
   sudo systemctl restart realtorvikkas
   ```

3. **Database Growing Too Large**
   ```bash
   # Check size
   du -sh /var/www/realtorvikkas/realtorvikkas.db
   
   # Compact database
   sqlite3 /var/www/realtorvikkas/realtorvikkas.db "VACUUM;"
   
   # If still large, enable WAL mode (already done by default)
   sqlite3 /var/www/realtorvikkas/realtorvikkas.db "PRAGMA journal_mode=WAL;"
   ```

---

### **High CPU Usage**

**Symptom:** CPU maxed out, app unresponsive

**Diagnosis:**
```bash
# Identify CPU-heavy processes
top -b -n 1 | head -15

# Check which queries are slow
grep "SLOW_QUERY" /var/www/realtorvikkas/performance.log | tail -10

# Check server load average
uptime
```

**Common Causes & Fixes:**

1. **Infinite Loop or Expensive Query**
   ```bash
   # Check recent errors
   tail -50 /var/www/realtorvikkas/error.log
   
   # Restart to clear
   sudo systemctl restart realtorvikkas
   ```

2. **Too Many Concurrent Requests**
   ```bash
   # Check active connections
   netstat -an | grep ESTABLISHED | grep 8000 | wc -l
   
   # If over 100, may need to scale
   # For now, restart to clear connections
   sudo systemctl restart realtorvikkas
   ```

3. **Database Needs Indexing**
   ```bash
   # Check which queries are slow
   grep "SLOW_QUERY.*SELECT" /var/www/realtorvikkas/performance.log | head -10
   
   # Verify indexes exist
   sqlite3 /var/www/realtorvikkas/realtorvikkas.db ".schema" | grep INDEX
   
   # Run ANALYZE
   sqlite3 /var/www/realtorvikkas/realtorvikkas.db "ANALYZE;"
   ```

---

### **High Memory Usage**

**Symptom:** Server running out of memory, apps getting killed

**Diagnosis:**
```bash
# Check memory usage
free -h

# Check which process is using memory
ps aux --sort=-%mem | head -10

# Check Python process memory
ps aux | grep python3
```

**Common Causes & Fixes:**

1. **Query Cache Growing Too Large**
   ```bash
   # Cache is in-memory (3600s TTL)
   # Clear by restarting
   sudo systemctl restart realtorvikkas
   
   # To reduce cache size, modify performance.py:
   # Change: _query_cache = QueryCache(ttl_seconds=3600)
   # To:     _query_cache = QueryCache(ttl_seconds=1800)
   ```

2. **Memory Leak**
   ```bash
   # Monitor memory over time
   watch -n 5 'ps aux | grep python3'
   
   # If steadily increasing, may have leak
   # Workaround: setup cron to restart periodically
   ```

3. **Not Enough Server Memory**
   ```bash
   # Check total available memory
   free -h
   
   # If <512MB, may need to upgrade server
   # Temporary workaround: reduce cache TTL
   ```

---

### **Nginx Issues**

**Symptom:** Can't access site, 502 Bad Gateway, or timeout errors

**Diagnosis:**
```bash
# Check Nginx status
sudo systemctl status nginx

# Check Nginx error log
sudo tail -20 /var/log/nginx/error.log

# Test Nginx configuration
sudo nginx -t

# Check if app is running
curl http://localhost:8000/
```

**Common Issues & Fixes:**

1. **Upstream Connection Refused (502)**
   ```bash
   # Application not running
   # Check if service is up
   sudo systemctl status realtorvikkas
   
   # If down, restart
   sudo systemctl restart realtorvikkas
   
   # Verify it's listening
   netstat -tlnp | grep 8000
   ```

2. **Connection Timeout**
   ```bash
   # Check if app is responding
   curl -v http://localhost:8000/
   
   # If hangs, restart app
   sudo systemctl restart realtorvikkas
   
   # Check database lock
   sqlite3 /var/www/realtorvikkas/realtorvikkas.db "PRAGMA busy_timeout = 5000;"
   ```

3. **Nginx Won't Start**
   ```bash
   # Test configuration
   sudo nginx -t
   
   # If error, check syntax
   sudo nginx -T
   
   # Fix configuration and reload
   sudo systemctl reload nginx
   ```

---

## 📈 MAINTENANCE TASKS

### **Daily Maintenance**

```bash
# ✅ Daily Checklist (5 minutes)

# 1. Check service is running
systemctl status realtorvikkas

# 2. Check recent errors
tail -50 /var/www/realtorvikkas/error.log

# 3. Monitor disk usage
df -h | grep "/var"

# 4. Check security events
grep "SECURITY_EVENT" /var/www/realtorvikkas/error.log | tail -10
```

### **Weekly Maintenance**

```bash
# ✅ Weekly Checklist (15 minutes)

# 1. Review performance metrics
echo "=== Performance Stats ==="
echo "Slow queries: $(grep -c "SLOW_QUERY" /var/www/realtorvikkas/performance.log)"
echo "Cache hits: $(grep -c "Cache hit" /var/www/realtorvikkas/performance.log)"
echo "Database size: $(ls -lh /var/www/realtorvikkas/realtorvikkas.db | awk '{print $5}')"

# 2. Backup database
cp /var/www/realtorvikkas/realtorvikkas.db /var/www/realtorvikkas/backups/realtorvikkas.db.backup.$(date +%Y%m%d)

# 3. Check error trends
grep "ERROR\|Exception" /var/www/realtorvikkas/error.log | wc -l

# 4. Review login attempts
grep "login" /var/www/realtorvikkas/auth.log | tail -50
```

### **Monthly Maintenance**

```bash
# ✅ Monthly Checklist (1 hour)

# 1. Full database optimization
sqlite3 /var/www/realtorvikkas/realtorvikkas.db << EOF
ANALYZE;
VACUUM;
EOF

# 2. Clean old logs (optional)
# System log rotation handles this via logrotate

# 3. Review all metrics
echo "=== Monthly Report ==="
echo "Total errors: $(grep -c "ERROR" /var/www/realtorvikkas/error.log)"
echo "Failed logins: $(grep -c "Failed login" /var/www/realtorvikkas/auth.log)"
echo "Lockouts: $(grep -c "locked out" /var/www/realtorvikkas/auth.log)"
echo "Slow queries: $(grep -c "SLOW_QUERY" /var/www/realtorvikkas/performance.log)"

# 4. Test backup restoration (quarterly)
# Verify backups can be restored

# 5. Check for security updates
apt list --upgradable | grep -i "python\|openssl"
```

---

## 🔐 SECURITY CHECKLIST

### **Authentication & Access**

- [ ] CSRF tokens are being generated (check logs)
- [ ] Rate limiting is active (5 attempts, 15 min lockout)
- [ ] Failed login attempts are logged
- [ ] Account lockouts are working
- [ ] Sessions have proper expiration (14 days)

### **Input Validation**

- [ ] SQL injection prevention active (sanitized queries)
- [ ] XSS protection enabled (HTML escaping)
- [ ] Email validation working
- [ ] Phone number validation working
- [ ] Password strength requirements enforced

### **Data Protection**

- [ ] Database backups scheduled
- [ ] Error logs don't expose sensitive data
- [ ] Passwords stored with PBKDF2 (not plaintext)
- [ ] Session tokens are random

### **Monitoring**

- [ ] Security events being logged
- [ ] Failed login attempts being tracked
- [ ] Unusual activity being alerted
- [ ] System resources being monitored

---

## 📞 ESCALATION CONTACTS

**Admin Email:** thevikkas@gmail.com  
**Server IP:** 216.24.57.1  
**Domain:** realtorvikkas.com  

### **On-Call Support Response Times**

- **Critical Issues** (down/data loss): 15 minutes
- **High Issues** (degraded performance): 1 hour
- **Medium Issues** (bugs/errors): 4 hours
- **Low Issues** (feature requests): Next business day

---

## 📋 QUICK REFERENCE

### Essential Commands
```bash
# Service Management
sudo systemctl start realtorvikkas
sudo systemctl stop realtorvikkas
sudo systemctl restart realtorvikkas
sudo systemctl status realtorvikkas

# Logs
tail -f /var/www/realtorvikkas/error.log
tail -f /var/www/realtorvikkas/performance.log
sudo journalctl -u realtorvikkas -f

# Database
sqlite3 /var/www/realtorvikkas/realtorvikkas.db "PRAGMA integrity_check;"
sqlite3 /var/www/realtorvikkas/realtorvikkas.db "VACUUM;"

# Monitoring
top
df -h
free -h
netstat -an | grep 8000
```

---

**Last Updated:** 2026-09-11  
**Version:** 1.0.0  
**Status:** 🟢 Production Ready
