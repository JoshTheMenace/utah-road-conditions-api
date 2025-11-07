#!/bin/bash
# Diagnostic script for UDOT detection timer issues

echo "========================================================================"
echo "UDOT Detection Timer Diagnostics"
echo "========================================================================"
echo ""

echo "1. Timer Status"
echo "----------------------------------------"
systemctl status udot-detection.timer --no-pager
echo ""

echo "2. Service Status (Last Run)"
echo "----------------------------------------"
systemctl status udot-detection.service --no-pager
echo ""

echo "3. Timer Schedule (When is next run?)"
echo "----------------------------------------"
systemctl list-timers udot-detection* --no-pager
echo ""

echo "4. Is Timer Enabled?"
echo "----------------------------------------"
systemctl is-enabled udot-detection.timer
echo ""

echo "5. Is Timer Active?"
echo "----------------------------------------"
systemctl is-active udot-detection.timer
echo ""

echo "6. Last 20 Log Lines (Service)"
echo "----------------------------------------"
journalctl -u udot-detection.service -n 20 --no-pager
echo ""

echo "7. Last 20 Log Lines (Timer)"
echo "----------------------------------------"
journalctl -u udot-detection.timer -n 20 --no-pager
echo ""

echo "8. Service Exit Status"
echo "----------------------------------------"
systemctl show udot-detection.service -p ExecMainStatus -p ActiveState -p SubState -p Result --no-pager
echo ""

echo "9. Check for Errors in Last Hour"
echo "----------------------------------------"
journalctl -u udot-detection.service --since "1 hour ago" -p err --no-pager
echo ""

echo "========================================================================"
echo "Diagnostic Complete"
echo "========================================================================"
echo ""
echo "Common Issues:"
echo "1. Timer not enabled -> Run: sudo systemctl enable udot-detection.timer"
echo "2. Service failed -> Check logs above for errors"
echo "3. Service still running -> OnUnitActiveSec waits until service completes"
echo "4. Timer not started -> Run: sudo systemctl start udot-detection.timer"
echo ""
