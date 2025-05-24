"""
Enhanced security monitoring for exams
"""
from datetime import datetime, timedelta
from flask import request, session
from sqlalchemy import and_, or_
from app import db
from app.models import ExamAttempt, SecurityLog
from app.security import log_security_event

class ExamSecurity:
    MAX_EVENT_SIZE = 10000  # Maximum size in bytes for event data
    SUSPICIOUS_PATTERNS = [
        {'type': 'MULTIPLE_IPS', 'threshold': 3, 'window_minutes': 60},
        {'type': 'RAPID_SWITCHES', 'threshold': 10, 'window_minutes': 5},
        {'type': 'FOCUS_LOSS', 'threshold': 5, 'window_minutes': 2},
    ]
    
    @classmethod
    def initialize_monitoring(cls, attempt):
        """Initialize security monitoring for an attempt"""
        attempt.environment_verified = False
        attempt.browser_fingerprint = cls._get_browser_fingerprint()
        attempt.ip_address = request.remote_addr
        attempt.user_agent = request.user_agent.string
        attempt.time_zone = request.headers.get('X-Timezone')
        attempt.security_events = []
        attempt.browser_events = []
        attempt.warning_events = []
        
        # Store initial state
        session[f'exam_security_{attempt.id}'] = {
            'initial_ip': request.remote_addr,
            'initial_fingerprint': attempt.browser_fingerprint,
            'warnings': 0,
            'last_check': datetime.utcnow().isoformat()
        }
        db.session.commit()
        
    @classmethod
    def log_security_event(cls, attempt, event_type, data, severity='info'):
        """Log a security event with validation"""
        # Validate and truncate data if needed
        if isinstance(data, dict):
            data_str = str(data)
            if len(data_str) > cls.MAX_EVENT_SIZE:
                data = {
                    'error': 'Event data truncated',
                    'original_type': event_type
                }
        
        timestamp = datetime.utcnow()
        
        # Create event entry
        event = {
            'type': event_type,
            'timestamp': timestamp.isoformat(),
            'data': data,
            'severity': severity,
            'ip_address': request.remote_addr,
            'user_agent': request.user_agent.string
        }
        
        # Update attempt events
        if not attempt.security_events:
            attempt.security_events = []
        attempt.security_events.append(event)
        
        # Create security log entry
        log = SecurityLog(
            event_type=event_type,
            description=str(data),
            user_id=attempt.student_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            severity=severity
        )
        db.session.add(log)
        
        # Check for suspicious patterns
        cls._check_suspicious_patterns(attempt)
        
        try:
            db.session.commit()
        except:
            db.session.rollback()
            raise
            
    @classmethod
    def validate_environment(cls, attempt):
        """Validate exam environment requirements"""
        checks = []
        
        # Browser checks
        checks.append({
            'type': 'browser_check',
            'passed': cls._validate_browser(attempt),
            'details': 'Browser security requirements'
        })
        
        # Network checks
        checks.append({
            'type': 'network_check',
            'passed': cls._validate_network(attempt),
            'details': 'Network security requirements'
        })
        
        # Device checks
        checks.append({
            'type': 'device_check',
            'passed': cls._validate_device(attempt),
            'details': 'Device security requirements'
        })
        
        # Store check results
        attempt.server_side_checks = checks
        attempt.environment_verified = all(check['passed'] for check in checks)
        
        if not attempt.environment_verified:
            cls.log_security_event(
                attempt,
                'ENVIRONMENT_CHECK_FAILED',
                {'checks': checks},
                'high'
            )
            
        return attempt.environment_verified
        
    @staticmethod
    def _get_browser_fingerprint():
        """Generate a browser fingerprint"""
        components = [
            request.user_agent.string,
            request.accept_languages,
            request.headers.get('Sec-Ch-Ua', ''),
            request.headers.get('Sec-Ch-Ua-Platform', '')
        ]
        return ':'.join(str(c) for c in components)
        
    @classmethod
    def _check_suspicious_patterns(cls, attempt):
        """Check for suspicious patterns in events"""
        now = datetime.utcnow()
        
        for pattern in cls.SUSPICIOUS_PATTERNS:
            window_start = now - timedelta(minutes=pattern['window_minutes'])
            
            # Count relevant events in window
            count = 0
            for event in attempt.security_events or []:
                event_time = datetime.fromisoformat(event['timestamp'])
                if event_time >= window_start and event['type'].startswith(pattern['type']):
                    count += 1
                    
            if count >= pattern['threshold']:
                cls.log_security_event(
                    attempt,
                    f'SUSPICIOUS_{pattern["type"]}',
                    {'count': count, 'window_minutes': pattern['window_minutes']},
                    'high'
                )
                attempt.verification_status = 'auto_flagged'
                
    @staticmethod
    def _validate_browser(attempt):
        """Validate browser security requirements"""
        if attempt.exam.require_lockdown and not attempt.secure_browser_active:
            return False
        if attempt.exam.require_webcam and not attempt.webcam_active:
            return False
        return True
        
    @staticmethod
    def _validate_network(attempt):
        """Validate network security requirements"""
        if attempt.exam.allowed_ip_range:
            import ipaddress
            try:
                network = ipaddress.ip_network(attempt.exam.allowed_ip_range)
                ip = ipaddress.ip_address(request.remote_addr)
                return ip in network
            except ValueError:
                return False
        return True
        
    @staticmethod
    def _validate_device(attempt):
        """Validate device security requirements"""
        if attempt.exam.block_virtual_machines:
            # Basic VM detection (can be enhanced)
            user_agent = request.user_agent.string.lower()
            vm_indicators = ['virtualbox', 'vmware', 'qemu', 'xen']
            return not any(ind in user_agent for ind in vm_indicators)
        return True
