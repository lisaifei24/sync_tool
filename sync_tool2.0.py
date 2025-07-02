import os
import shutil
import sys
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QListWidget, QLabel, QLineEdit, 
                             QSpinBox, QTextEdit, QFileDialog, QWidget, 
                             QMessageBox, QInputDialog, QGroupBox, QCheckBox,
                             QComboBox, QTabWidget, QTableWidget, QTableWidgetItem)
from PyQt5.QtCore import QTimer, Qt, QDate

class SyncHandler(FileSystemEventHandler):
    def __init__(self, sync_tool):
        super().__init__()
        self.sync_tool = sync_tool
    
    def on_modified(self, event):
        if not event.is_directory:
            self.sync_tool.log(f"检测到文件修改: {event.src_path}")
            self.sync_tool.sync_files()

class FileSyncTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("高级文件同步工具")
        self.setGeometry(100, 100, 1000, 800)
        
        # 初始化变量
        self.sync_paths = []
        self.observer = None
        self.sync_handler = SyncHandler(self)
        self.last_sync_time = None
        self.sync_history = []
        self.conflict_resolution = "newer"  # newer, larger, ask
        self.sync_direction = "bidirectional"  # bidirectional, source_to_dest, dest_to_source
        self.file_filters = {
            'extensions': [],
            'min_size': 0,
            'max_size': 0,
            'exclude_hidden': True
        }
        
        # 创建UI
        self.init_ui()
        
        # 设置定时器
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.sync_files)
        
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # 使用选项卡组织功能
        self.tabs = QTabWidget()
        
        # 基本同步选项卡
        self.setup_basic_tab()
        
        # 高级设置选项卡
        self.setup_advanced_tab()
        
        # 历史记录选项卡
        self.setup_history_tab()
        
        main_layout.addWidget(self.tabs)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # 初始状态
        self.update_buttons_state()
        
    def setup_basic_tab(self):
        basic_tab = QWidget()
        layout = QVBoxLayout()
        
        # 路径管理部分
        path_group = QGroupBox("路径管理")
        path_layout = QHBoxLayout()
        
        self.path_list = QListWidget()
        self.path_list.setSelectionMode(QListWidget.SingleSelection)
        path_layout.addWidget(self.path_list)
        
        btn_layout = QVBoxLayout()
        self.add_btn = QPushButton("添加路径")
        self.add_btn.clicked.connect(self.add_path)
        btn_layout.addWidget(self.add_btn)
        
        self.remove_btn = QPushButton("移除路径")
        self.remove_btn.clicked.connect(self.remove_path)
        btn_layout.addWidget(self.remove_btn)
        
        path_layout.addLayout(btn_layout)
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)
        
        # 同步控制部分
        control_group = QGroupBox("同步控制")
        control_layout = QHBoxLayout()
        
        control_layout.addWidget(QLabel("同步间隔(秒):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 3600)
        self.interval_spin.setValue(60)
        control_layout.addWidget(self.interval_spin)
        
        self.start_btn = QPushButton("开始监控")
        self.start_btn.clicked.connect(self.start_monitoring)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止监控")
        self.stop_btn.clicked.connect(self.stop_monitoring)
        control_layout.addWidget(self.stop_btn)
        
        self.sync_now_btn = QPushButton("立即同步")
        self.sync_now_btn.clicked.connect(self.sync_files)
        control_layout.addWidget(self.sync_now_btn)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # 日志部分
        log_group = QGroupBox("同步日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        basic_tab.setLayout(layout)
        self.tabs.addTab(basic_tab, "基本同步")
    
    def setup_advanced_tab(self):
        advanced_tab = QWidget()
        layout = QVBoxLayout()
        
        # 同步方向设置
        direction_group = QGroupBox("同步方向")
        direction_layout = QVBoxLayout()
        
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("双向同步 (保持所有位置一致)", "bidirectional")
        self.direction_combo.addItem("源到目标 (源覆盖目标)", "source_to_dest")
        self.direction_combo.addItem("目标到源 (目标覆盖源)", "dest_to_source")
        self.direction_combo.currentIndexChanged.connect(self.update_sync_direction)
        direction_layout.addWidget(self.direction_combo)
        
        direction_group.setLayout(direction_layout)
        layout.addWidget(direction_group)
        
        # 冲突解决设置
        conflict_group = QGroupBox("冲突解决")
        conflict_layout = QVBoxLayout()
        
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItem("保留较新的文件", "newer")
        self.conflict_combo.addItem("保留较大的文件", "larger")
        self.conflict_combo.addItem("每次询问", "ask")
        self.conflict_combo.currentIndexChanged.connect(self.update_conflict_resolution)
        conflict_layout.addWidget(self.conflict_combo)
        
        conflict_group.setLayout(conflict_layout)
        layout.addWidget(conflict_group)
        
        # 文件过滤设置
        filter_group = QGroupBox("文件过滤")
        filter_layout = QVBoxLayout()
        
        # 扩展名过滤
        ext_layout = QHBoxLayout()
        ext_layout.addWidget(QLabel("文件扩展名(逗号分隔):"))
        self.ext_edit = QLineEdit()
        ext_layout.addWidget(self.ext_edit)
        filter_layout.addLayout(ext_layout)
        
        # 文件大小过滤
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("文件大小范围(KB):"))
        
        self.min_size_edit = QLineEdit()
        self.min_size_edit.setPlaceholderText("最小")
        size_layout.addWidget(self.min_size_edit)
        
        self.max_size_edit = QLineEdit()
        self.max_size_edit.setPlaceholderText("最大")
        size_layout.addWidget(self.max_size_edit)
        filter_layout.addLayout(size_layout)
        
        # 其他过滤选项
        self.exclude_hidden_check = QCheckBox("排除隐藏文件")
        self.exclude_hidden_check.setChecked(True)
        filter_layout.addWidget(self.exclude_hidden_check)
        
        # 应用过滤按钮
        self.apply_filter_btn = QPushButton("应用过滤设置")
        self.apply_filter_btn.clicked.connect(self.apply_file_filters)
        filter_layout.addWidget(self.apply_filter_btn)
        
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        advanced_tab.setLayout(layout)
        self.tabs.addTab(advanced_tab, "高级设置")
    
    def setup_history_tab(self):
        history_tab = QWidget()
        layout = QVBoxLayout()
        
        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(["时间", "操作", "文件数", "状态"])
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.history_table)
        
        # 历史记录操作按钮
        btn_layout = QHBoxLayout()
        self.clear_history_btn = QPushButton("清除历史")
        self.clear_history_btn.clicked.connect(self.clear_history)
        btn_layout.addWidget(self.clear_history_btn)
        
        self.export_history_btn = QPushButton("导出历史")
        self.export_history_btn.clicked.connect(self.export_history)
        btn_layout.addWidget(self.export_history_btn)
        
        layout.addLayout(btn_layout)
        
        history_tab.setLayout(layout)
        self.tabs.addTab(history_tab, "同步历史")
    
    def update_sync_direction(self):
        self.sync_direction = self.direction_combo.currentData()
        self.log(f"同步方向设置为: {self.direction_combo.currentText()}")
    
    def update_conflict_resolution(self):
        self.conflict_resolution = self.conflict_combo.currentData()
        self.log(f"冲突解决策略设置为: {self.conflict_combo.currentText()}")
    
    def apply_file_filters(self):
        extensions = self.ext_edit.text().strip()
        if extensions:
            self.file_filters['extensions'] = [ext.strip().lower() for ext in extensions.split(',')]
        else:
            self.file_filters['extensions'] = []
        
        try:
            self.file_filters['min_size'] = int(self.min_size_edit.text()) * 1024 if self.min_size_edit.text() else 0
            self.file_filters['max_size'] = int(self.max_size_edit.text()) * 1024 if self.max_size_edit.text() else 0
        except ValueError:
            QMessageBox.warning(self, "警告", "文件大小必须为整数!")
            return
        
        self.file_filters['exclude_hidden'] = self.exclude_hidden_check.isChecked()
        
        self.log("文件过滤设置已更新:")
        self.log(f"扩展名: {self.file_filters['extensions'] or '无限制'}")
        self.log(f"大小范围: {self.file_filters['min_size']/1024 if self.file_filters['min_size'] else 0}KB - "
                f"{self.file_filters['max_size']/1024 if self.file_filters['max_size'] else '∞'}KB")
        self.log(f"排除隐藏文件: {'是' if self.file_filters['exclude_hidden'] else '否'}")
    
    def file_passes_filters(self, file_path):
        # 检查扩展名
        if self.file_filters['extensions']:
            ext = os.path.splitext(file_path)[1].lower().lstrip('.')
            if ext not in self.file_filters['extensions']:
                return False
        
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if self.file_filters['min_size'] and file_size < self.file_filters['min_size']:
            return False
        if self.file_filters['max_size'] and file_size > self.file_filters['max_size']:
            return False
        
        # 检查隐藏文件
        if self.file_filters['exclude_hidden'] and os.path.basename(file_path).startswith('.'):
            return False
        
        return True
    
    def update_buttons_state(self):
        has_paths = len(self.sync_paths) > 0
        self.start_btn.setEnabled(has_paths)
        self.sync_now_btn.setEnabled(has_paths)
        self.remove_btn.setEnabled(has_paths and self.path_list.currentRow() >= 0)
        
    def add_path(self):
        options = QFileDialog.Options()
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "All Files (*)", options=options)
        if not path:
            path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        
        if path:
            if path not in self.sync_paths:
                reply = QMessageBox.question(self, '确认', f'确定要添加路径: {path}?', 
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.sync_paths.append(path)
                    self.path_list.addItem(path)
                    self.update_buttons_state()
                    self.log(f"添加路径: {path}")
            else:
                QMessageBox.information(self, "提示", "该路径已存在!")
    
    def remove_path(self):
        current_row = self.path_list.currentRow()
        if current_row >= 0:
            item = self.path_list.item(current_row)
            path = item.text()
            
            reply = QMessageBox.question(self, '确认', f'确定要移除路径: {path}?', 
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.path_list.takeItem(current_row)
                if path in self.sync_paths:
                    self.sync_paths.remove(path)
                self.log(f"移除路径: {path}")
                self.update_buttons_state()
    
    def start_monitoring(self):
        if len(self.sync_paths) < 2:
            QMessageBox.warning(self, "警告", "至少需要两个路径才能同步!")
            return
            
        interval = self.interval_spin.value() * 1000  # 转换为毫秒
        self.sync_timer.start(interval)
        
        # 启动文件监控
        if self.observer is None:
            self.observer = Observer()
            for path in self.sync_paths:
                if os.path.isdir(path):
                    self.observer.schedule(self.sync_handler, path, recursive=True)
            self.observer.start()
        
        self.log(f"开始监控，同步间隔: {self.interval_spin.value()}秒")
        self.update_buttons_state()
    
    def stop_monitoring(self):
        self.sync_timer.stop()
        
        if self.observer:
            self.observer.stop()
            self.observer = None
        
        self.log("停止监控")
        self.update_buttons_state()
    
    def resolve_conflict(self, src_path, dest_path):
        if self.conflict_resolution == "ask":
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setText("发现文件冲突，请选择操作:")
            msg.setWindowTitle("文件冲突")
            msg.setDetailedText(f"源文件: {src_path}\n修改时间: {datetime.fromtimestamp(os.path.getmtime(src_path))}\n大小: {os.path.getsize(src_path)} bytes\n\n"
                              f"目标文件: {dest_path}\n修改时间: {datetime.fromtimestamp(os.path.getmtime(dest_path))}\n大小: {os.path.getsize(dest_path)} bytes")
            
            keep_src_btn = msg.addButton("保留源文件", QMessageBox.AcceptRole)
            keep_dest_btn = msg.addButton("保留目标文件", QMessageBox.RejectRole)
            cancel_btn = msg.addButton("取消", QMessageBox.DestructiveRole)
            
            msg.exec_()
            
            if msg.clickedButton() == keep_src_btn:
                return "source"
            elif msg.clickedButton() == keep_dest_btn:
                return "destination"
            else:
                return "skip"
        elif self.conflict_resolution == "newer":
            src_mtime = os.path.getmtime(src_path)
            dest_mtime = os.path.getmtime(dest_path)
            return "source" if src_mtime > dest_mtime else "destination"
        else:  # larger
            src_size = os.path.getsize(src_path)
            dest_size = os.path.getsize(dest_path)
            return "source" if src_size > dest_size else "destination"
    
    def sync_files(self):
        if len(self.sync_paths) < 2:
            return
            
        self.log("开始同步文件...")
        start_time = datetime.now()
        file_count = 0
        success = True
        
        try:
            # 单向同步逻辑
            if self.sync_direction in ["source_to_dest", "dest_to_source"]:
                source_idx = 0 if self.sync_direction == "source_to_dest" else 1
                dest_idx = 1 if self.sync_direction == "source_to_dest" else 0
                
                source = self.sync_paths[source_idx]
                destination = self.sync_paths[dest_idx]
                
                if os.path.isfile(source) and os.path.isfile(destination):
                    # 文件同步
                    if self.file_passes_filters(source):
                        shutil.copy2(source, destination)
                        file_count += 1
                        self.log(f"同步文件: 从 {source} 到 {destination}")
                elif os.path.isdir(source) and os.path.isdir(destination):
                    # 文件夹同步
                    for root, _, files in os.walk(source):
                        rel_path = os.path.relpath(root, source)
                        dest_dir = os.path.join(destination, rel_path)
                        
                        if not os.path.exists(dest_dir):
                            os.makedirs(dest_dir)
                        
                        for file in files:
                            src_file = os.path.join(root, file)
                            if self.file_passes_filters(src_file):
                                dest_file = os.path.join(dest_dir, file)
                                
                                if not os.path.exists(dest_file) or os.path.getmtime(src_file) > os.path.getmtime(dest_file):
                                    shutil.copy2(src_file, dest_file)
                                    file_count += 1
                                    self.log(f"同步文件: 从 {src_file} 到 {dest_file}")
            else:
                # 双向同步逻辑
                all_files = {}
                
                # 收集所有文件信息
                for path in self.sync_paths:
                    if os.path.isfile(path):
                        if self.file_passes_filters(path):
                            filename = os.path.basename(path)
                            mtime = os.path.getmtime(path)
                            size = os.path.getsize(path)
                            
                            if filename not in all_files or mtime > all_files[filename]['mtime']:
                                all_files[filename] = {
                                    'path': path,
                                    'mtime': mtime,
                                    'size': size
                                }
                    elif os.path.isdir(path):
                        for root, _, files in os.walk(path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                if self.file_passes_filters(file_path):
                                    rel_path = os.path.relpath(file_path, path)
                                    mtime = os.path.getmtime(file_path)
                                    size = os.path.getsize(file_path)
                                    
                                    if rel_path not in all_files or mtime > all_files[rel_path]['mtime']:
                                        all_files[rel_path] = {
                                            'path': file_path,
                                            'mtime': mtime,
                                            'size': size,
                                            'source_path': path
                                        }
                
                # 执行同步
                for rel_path, file_info in all_files.items():
                    for path in self.sync_paths:
                        if os.path.isdir(path):
                            dest_path = os.path.join(path, rel_path)
                            if not os.path.exists(dest_path) or os.path.getmtime(file_info['path']) > os.path.getmtime(dest_path):
                                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                                shutil.copy2(file_info['path'], dest_path)
                                file_count += 1
                                self.log(f"同步文件: 从 {file_info['path']} 到 {dest_path}")
                        elif os.path.isfile(path) and path != file_info['path']:
                            resolution = self.resolve_conflict(file_info['path'], path)
                            if resolution == "source":
                                shutil.copy2(file_info['path'], path)
                                file_count += 1
                                self.log(f"同步文件(冲突解决): 从 {file_info['path']} 到 {path}")
                            elif resolution == "destination":
                                shutil.copy2(path, file_info['path'])
                                file_count += 1
                                self.log(f"同步文件(冲突解决): 从 {path} 到 {file_info['path']}")
            
            self.last_sync_time = datetime.now()
            status = f"成功同步 {file_count} 个文件"
            self.log(f"同步完成: {status}")
        except Exception as e:
            status = f"同步失败: {str(e)}"
            self.log(status)
            success = False
        
        # 记录历史
        self.record_sync_history(start_time, datetime.now(), file_count, status)
        self.update_history_table()
        
        return success
    
    def record_sync_history(self, start_time, end_time, file_count, status):
        self.sync_history.append({
            'start': start_time,
            'end': end_time,
            'file_count': file_count,
            'status': status,
            'paths': self.sync_paths.copy()
        })
    
    def update_history_table(self):
        self.history_table.setRowCount(len(self.sync_history))
        
        for row, record in enumerate(self.sync_history):
            self.history_table.setItem(row, 0, QTableWidgetItem(record['start'].strftime('%Y-%m-%d %H:%M:%S')))
            self.history_table.setItem(row, 1, QTableWidgetItem(f"{len(record['paths'])}个路径"))
            self.history_table.setItem(row, 2, QTableWidgetItem(str(record['file_count'])))
            self.history_table.setItem(row, 3, QTableWidgetItem(record['status']))
    
    def clear_history(self):
        self.sync_history.clear()
        self.history_table.setRowCount(0)
        self.log("已清除同步历史记录")
    
    def export_history(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "导出历史记录", "", "CSV Files (*.csv)", options=options)
        
        if file_name:
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write("开始时间,结束时间,路径数量,文件数量,状态,路径\n")
                    for record in self.sync_history:
                        paths = ';'.join(record['paths'])
                        f.write(f"{record['start'].strftime('%Y-%m-%d %H:%M:%S')},"
                               f"{record['end'].strftime('%Y-%m-%d %H:%M:%S')},"
                               f"{len(record['paths'])},{record['file_count']},"
                               f"{record['status']},\"{paths}\"\n")
                self.log(f"历史记录已导出到: {file_name}")
            except Exception as e:
                QMessageBox.warning(self, "导出失败", f"无法导出历史记录: {str(e)}")
    
    def log(self, message):
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        self.log_text.append(f"{timestamp} {message}")
    
    def closeEvent(self, event):
        self.stop_monitoring()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    sync_tool = FileSyncTool()
    sync_tool.show()
    sys.exit(app.exec_())