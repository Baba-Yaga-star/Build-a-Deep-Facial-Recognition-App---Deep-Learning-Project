import json
import os
import pandas as pd
from datetime import datetime, timedelta
import cv2
import numpy as np

class AttendanceUtils:
    """Các hàm tiện ích cho hệ thống điểm danh"""
    
    def __init__(self, log_file="attendance_logs/attendance.json"):
        self.log_file = log_file
        
    def load_attendance_data(self):
        """Load dữ liệu điểm danh từ file JSON"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def get_attendance_by_date(self, date_str):
        """Lấy điểm danh theo ngày cụ thể (YYYY-MM-DD)"""
        data = self.load_attendance_data()
        return [entry for entry in data if entry.get('date') == date_str]
    
    def get_attendance_by_date_range(self, start_date, end_date):
        """Lấy điểm danh theo khoảng thời gian"""
        data = self.load_attendance_data()
        result = []
        
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        for entry in data:
            entry_date = datetime.strptime(entry.get('date'), "%Y-%m-%d").date()
            if start <= entry_date <= end:
                result.append(entry)
                
        return result
    
    def get_weekly_report(self):
        """Báo cáo tuần này"""
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        return self.get_attendance_by_date_range(
            start_of_week.strftime("%Y-%m-%d"),
            end_of_week.strftime("%Y-%m-%d")
        )
    
    def get_monthly_report(self):
        """Báo cáo tháng này"""
        today = datetime.now().date()
        start_of_month = today.replace(day=1)
        
        # Ngày cuối tháng
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        
        return self.get_attendance_by_date_range(
            start_of_month.strftime("%Y-%m-%d"),
            end_of_month.strftime("%Y-%m-%d")
        )
    
    def calculate_working_hours(self, name, date_str):
        """Tính giờ làm việc của 1 người trong 1 ngày"""
        day_data = self.get_attendance_by_date(date_str)
        person_data = [entry for entry in day_data if entry['name'] == name]
        
        if len(person_data) < 2:
            return 0
        
        # Sắp xếp theo thời gian
        person_data.sort(key=lambda x: x['timestamp'])
        
        total_hours = 0
        in_time = None
        
        for entry in person_data:
            if entry['action'] == 'IN':
                in_time = datetime.strptime(entry['timestamp'], "%Y-%m-%d %H:%M:%S")
            elif entry['action'] == 'OUT' and in_time:
                out_time = datetime.strptime(entry['timestamp'], "%Y-%m-%d %H:%M:%S")
                hours = (out_time - in_time).total_seconds() / 3600
                total_hours += hours
                in_time = None
        
        return round(total_hours, 2)
    
    def get_summary_report(self, start_date, end_date):
        """Báo cáo tổng hợp theo khoảng thời gian"""
        data = self.get_attendance_by_date_range(start_date, end_date)
        
        # Group by name
        summary = {}
        
        # Lấy tất cả ngày trong khoảng
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        current_date = start
        all_dates = []
        while current_date <= end:
            all_dates.append(current_date.strftime("%Y-%m-%d"))
            current_date += timedelta(days=1)
        
        # Lấy danh sách tất cả nhân viên
        all_names = list(set([entry['name'] for entry in data]))
        
        for name in all_names:
            summary[name] = {
                'name': name,
                'total_days': 0,
                'total_hours': 0,
                'days_detail': {}
            }
            
            for date in all_dates:
                hours = self.calculate_working_hours(name, date)
                if hours > 0:
                    summary[name]['total_days'] += 1
                    summary[name]['total_hours'] += hours
                    summary[name]['days_detail'][date] = hours
        
        return summary
    
    def export_to_excel(self, start_date, end_date, filename=None):
        """Export báo cáo ra Excel"""
        try:
            import pandas as pd
            
            if not filename:
                filename = f"attendance_report_{start_date}_to_{end_date}.xlsx"
            
            # Lấy dữ liệu chi tiết
            data = self.get_attendance_by_date_range(start_date, end_date)
            
            # Tạo DataFrame cho dữ liệu thô
            df_raw = pd.DataFrame(data)
            
            # Tạo báo cáo tổng hợp
            summary = self.get_summary_report(start_date, end_date)
            
            summary_data = []
            for name, info in summary.items():
                summary_data.append({
                    'Tên': info['name'],
                    'Tổng ngày làm': info['total_days'],
                    'Tổng giờ làm': info['total_hours']
                })
            
            df_summary = pd.DataFrame(summary_data)
            
            # Ghi vào Excel với nhiều sheet
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df_raw.to_excel(writer, sheet_name='Chi tiết', index=False)
                df_summary.to_excel(writer, sheet_name='Tổng hợp', index=False)
            
            return filename
            
        except ImportError:
            print("❌ Cần cài pandas và openpyxl: pip install pandas openpyxl")
            return None
        except Exception as e:
            print(f"❌ Lỗi export Excel: {e}")
            return None
    
    def get_late_arrivals(self, date_str, standard_time="08:30"):
        """Lấy danh sách người đến muộn"""
        day_data = self.get_attendance_by_date(date_str)
        late_people = []
        
        standard_dt = datetime.strptime(f"{date_str} {standard_time}", "%Y-%m-%d %H:%M")
        
        # Group theo tên
        people_in = {}
        for entry in day_data:
            if entry['action'] == 'IN':
                name = entry['name']
                entry_time = datetime.strptime(entry['timestamp'], "%Y-%m-%d %H:%M:%S")
                
                if name not in people_in or entry_time < people_in[name]:
                    people_in[name] = entry_time
        
        # Kiểm tra ai đến muộn
        for name, time in people_in.items():
            if time > standard_dt:
                minutes_late = (time - standard_dt).total_seconds() / 60
                late_people.append({
                    'name': name,
                    'arrival_time': time.strftime("%H:%M:%S"),
                    'minutes_late': int(minutes_late)
                })
        
        return sorted(late_people, key=lambda x: x['minutes_late'], reverse=True)
    
    def get_early_departures(self, date_str, standard_time="17:30"):
        """Lấy danh sách người về sớm"""
        day_data = self.get_attendance_by_date(date_str)
        early_people = []
        
        standard_dt = datetime.strptime(f"{date_str} {standard_time}", "%Y-%m-%d %H:%M")
        
        # Group theo tên
        people_out = {}
        for entry in day_data:
            if entry['action'] == 'OUT':
                name = entry['name']
                entry_time = datetime.strptime(entry['timestamp'], "%Y-%m-%d %H:%M:%S")
                
                if name not in people_out or entry_time > people_out[name]:
                    people_out[name] = entry_time
        
        # Kiểm tra ai về sớm
        for name, time in people_out.items():
            if time < standard_dt:
                minutes_early = (standard_dt - time).total_seconds() / 60
                early_people.append({
                    'name': name,
                    'departure_time': time.strftime("%H:%M:%S"),
                    'minutes_early': int(minutes_early)
                })
        
        return sorted(early_people, key=lambda x: x['minutes_early'], reverse=True)
    
    def backup_data(self, backup_dir="backup"):
        """Backup dữ liệu điểm danh"""
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"attendance_backup_{timestamp}.json")
        
        try:
            data = self.load_attendance_data()
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return backup_file
        except Exception as e:
            print(f"❌ Lỗi backup: {e}")
            return None
    
    def clean_duplicate_entries(self):
        """Xóa các entry trùng lặp (cùng người, cùng thời gian)"""
        data = self.load_attendance_data()
        seen = set()
        cleaned_data = []
        
        for entry in data:
            # Tạo key unique
            key = f"{entry['name']}_{entry['timestamp']}_{entry['action']}"
            
            if key not in seen:
                seen.add(key)
                cleaned_data.append(entry)
        
        # Lưu lại dữ liệu đã clean
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
            
            removed_count = len(data) - len(cleaned_data)
            print(f"✅ Đã xóa {removed_count} entry trùng lặp")
            return removed_count
        except Exception as e:
            print(f"❌ Lỗi clean data: {e}")
            return 0


class ImageUtils:
    """Các hàm tiện ích xử lý ảnh"""
    
    @staticmethod
    def resize_image(image_path, output_path, size=(105, 105)):
        """Resize ảnh về kích thước chuẩn"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return False
                
            resized = cv2.resize(img, size)
            cv2.imwrite(output_path, resized)
            return True
        except Exception as e:
            print(f"❌ Lỗi resize ảnh: {e}")
            return False
    
    @staticmethod
    def batch_resize_images(input_dir, output_dir, size=(105, 105)):
        """Resize hàng loạt ảnh trong thư mục"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        count = 0
        for filename in os.listdir(input_dir):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                input_path = os.path.join(input_dir, filename)
                output_path = os.path.join(output_dir, filename)
                
                if ImageUtils.resize_image(input_path, output_path, size):
                    count += 1
        
        print(f"✅ Đã resize {count} ảnh")
        return count
    
    @staticmethod
    def validate_face_image(image_path):
        """Kiểm tra ảnh có hợp lệ cho nhận diện không"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return False, "Không thể đọc ảnh"
            
            # Kiểm tra kích thước
            height, width = img.shape[:2]
            if width < 50 or height < 50:
                return False, "Ảnh quá nhỏ"
            
            # Có thể thêm kiểm tra face detection ở đây
            # face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            # faces = face_cascade.detectMultiScale(img, 1.1, 4)
            # if len(faces) == 0:
            #     return False, "Không phát hiện khuôn mặt"
            
            return True, "Ảnh hợp lệ"
            
        except Exception as e:
            return False, f"Lỗi: {e}"


# Ví dụ sử dụng
if __name__ == "__main__":
    # Test các function
    utils = AttendanceUtils()
    
    print("📊 Demo AttendanceUtils:")
    print("=" * 50)
    
    # Test lấy dữ liệu hôm nay
    today = datetime.now().strftime("%Y-%m-%d")
    today_data = utils.get_attendance_by_date(today)
    print(f"📅 Điểm danh hôm nay ({today}): {len(today_data)} records")
    
    # Test báo cáo tuần
    weekly = utils.get_weekly_report()
    print(f"📈 Báo cáo tuần này: {len(weekly)} records")
    
    # Test backup
    backup_file = utils.backup_data()
    if backup_file:
        print(f"💾 Backup thành công: {backup_file}")
    
    # Test clean duplicate
    removed = utils.clean_duplicate_entries()
    print(f"🧹 Đã xóa {removed} records trùng lặp")