#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MDSplus Database Monitor
Real-time monitoring of shot numbers and channel status in MDSplus database
"""

import time
import sys
import os
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, font
import locale

# Import MDSplus connection modules
from RunDetectAlgorithm.mdsConn import MdsConn, MdsTree, currentShot, formChaPool, DBS


class MDSMonitor:
    """MDSplus database monitoring class for shots and channels status"""
    
    def __init__(self, db_name='exl50u', update_interval=5, max_shots=10):
        """
        Initialize the monitor
        
        Parameters:
            db_name (str): Database name, must be defined in DBS dictionary
            update_interval (int): Update interval in seconds
            max_shots (int): Maximum number of shots to display
        """
        if db_name not in DBS:
            raise ValueError(f"Database '{db_name}' not in known database list")
            
        self.db_name = db_name
        self.db_info = DBS[db_name]
        self.update_interval = update_interval
        self.max_shots = max_shots
        
        # Connect to database
        self.conn = MdsConn(self.db_name, self.db_info['addr'])
        
        # Status variables
        self.current_shot = None
        self.previous_shots = []
        self.channels = []
        self.channel_status = {}
        self.running = False
        self.monitor_thread = None
        
        # Initialize GUI
        self.setup_gui()
        
    def setup_gui(self):
        """Set up the graphical user interface"""
        self.root = tk.Tk()
        self.root.title(f"MDSplus Database Monitor - {self.db_name}")
        self.root.geometry("1200x800")
        
        # Configure default font
        default_font = ('TkDefaultFont', 12)
        
        # Configure default style
        style = ttk.Style()
        style.configure("TLabel", font=default_font)
        style.configure("TButton", font=default_font)
        style.configure("TCombobox", font=default_font)
        style.configure("Treeview", font=default_font)
        style.configure("Treeview.Heading", font=default_font)
        
        # Create top information bar
        info_frame = ttk.Frame(self.root, padding=10)
        info_frame.pack(fill=tk.X)
        
        ttk.Label(info_frame, text=f"Database: {self.db_name}", font=(default_font[0], 12, 'bold')).pack(side=tk.LEFT, padx=5)
        ttk.Label(info_frame, text=f"Address: {self.db_info['addr']}", font=(default_font[0], 12)).pack(side=tk.LEFT, padx=5)
        
        self.status_label = ttk.Label(info_frame, text="Status: Not Started", font=(default_font[0], 12))
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
        # Create button bar
        button_frame = ttk.Frame(self.root, padding=10)
        button_frame.pack(fill=tk.X)
        
        self.start_button = ttk.Button(button_frame, text="Start Monitoring", command=self.start_monitoring)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop Monitoring", command=self.stop_monitoring, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.refresh_button = ttk.Button(button_frame, text="Refresh", command=self.refresh_data)
        self.refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Create database selection dropdown
        ttk.Label(button_frame, text="Select Database:", font=default_font).pack(side=tk.LEFT, padx=5)
        self.db_var = tk.StringVar(value=self.db_name)
        db_combo = ttk.Combobox(button_frame, textvariable=self.db_var, values=list(DBS.keys()), state="readonly")
        db_combo.pack(side=tk.LEFT, padx=5)
        db_combo.bind("<<ComboboxSelected>>", self.change_database)
        
        # Create shot display area
        self.create_shot_frame(default_font)
        
        # Create channel status table
        self.create_channel_treeview(default_font)
        
        # Create statistics area
        self.create_stats_frame(default_font)
        
        # Set window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def create_shot_frame(self, default_font):
        """Create shot information display area"""
        shot_frame = ttk.LabelFrame(self.root, text="Shot Information", padding=10)
        shot_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Current shot display
        current_shot_frame = ttk.Frame(shot_frame)
        current_shot_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(current_shot_frame, text="Current Shot:", font=(default_font[0], 12, 'bold')).pack(side=tk.LEFT, padx=5)
        self.shot_label = ttk.Label(current_shot_frame, text="Loading...", font=(default_font[0], 14, 'bold'))
        self.shot_label.pack(side=tk.LEFT, padx=5)
        
        # Recent shots list
        recent_shot_frame = ttk.Frame(shot_frame)
        recent_shot_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(recent_shot_frame, text="Recent Shots:", font=(default_font[0], 12)).pack(side=tk.LEFT, padx=5)
        self.recent_shots_label = ttk.Label(recent_shot_frame, text="No Records", font=(default_font[0], 12))
        self.recent_shots_label.pack(side=tk.LEFT, padx=5)
        
        # Update time
        update_time_frame = ttk.Frame(shot_frame)
        update_time_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(update_time_frame, text="Last Update:", font=(default_font[0], 12)).pack(side=tk.LEFT, padx=5)
        self.update_time_label = ttk.Label(update_time_frame, text="Not Updated", font=(default_font[0], 12))
        self.update_time_label.pack(side=tk.LEFT, padx=5)
        
    def create_channel_treeview(self, default_font):
        """Create channel status table"""
        channel_frame = ttk.LabelFrame(self.root, text="Channel Status", padding=10)
        channel_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create search box
        search_frame = ttk.Frame(channel_frame)
        search_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(search_frame, text="Search Channel:", font=default_font).pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30, font=default_font)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_var.trace("w", self.filter_channels)
        
        # Create filter options
        self.filter_var = tk.StringVar(value="All")
        filter_options = ["All", "Has Data", "No Data", "Error"]
        ttk.Label(search_frame, text="Filter:", font=default_font).pack(side=tk.LEFT, padx=5)
        filter_combo = ttk.Combobox(search_frame, textvariable=self.filter_var, values=filter_options, state="readonly", width=10)
        filter_combo.pack(side=tk.LEFT, padx=5)
        filter_combo.bind("<<ComboboxSelected>>", lambda e: self.filter_channels())
        
        # Create Treeview
        columns = ("Channel", "Status", "Data Length", "Update Time")
        self.tree = ttk.Treeview(channel_frame, columns=columns, show="headings")
        
        # Set column headers
        for col in columns:
            self.tree.heading(col, text=col)
            
        # Set column widths
        self.tree.column("Channel", width=250)
        self.tree.column("Status", width=100)
        self.tree.column("Data Length", width=100)
        self.tree.column("Update Time", width=200)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(channel_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
    def create_stats_frame(self, default_font):
        """Create statistics area"""
        stats_frame = ttk.LabelFrame(self.root, text="Channel Statistics", padding=10)
        stats_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Create statistics labels
        self.total_label = ttk.Label(stats_frame, text="Total Channels: 0", font=(default_font[0], 12))
        self.total_label.pack(side=tk.LEFT, padx=20)
        
        self.with_data_label = ttk.Label(stats_frame, text="With Data: 0", font=(default_font[0], 12))
        self.with_data_label.pack(side=tk.LEFT, padx=20)
        
        self.no_data_label = ttk.Label(stats_frame, text="No Data: 0", font=(default_font[0], 12))
        self.no_data_label.pack(side=tk.LEFT, padx=20)
        
        self.error_label = ttk.Label(stats_frame, text="Errors: 0", font=(default_font[0], 12))
        self.error_label.pack(side=tk.LEFT, padx=20)
        
    def start_monitoring(self):
        """Start monitoring the database"""
        if not self.running:
            self.running = True
            self.status_label.config(text="Status: Monitoring")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            
            # Start the monitoring thread
            self.monitor_thread = threading.Thread(target=self.monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop monitoring the database"""
        self.running = False
        self.status_label.config(text="Status: Stopped")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def refresh_data(self):
        """Manually refresh data"""
        self.check_current_shot()
        self.update_channel_status()
        self.update_time_label.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    def change_database(self, event):
        """Switch the monitored database"""
        new_db = self.db_var.get()
        if new_db != self.db_name:
            # If monitoring, stop first
            if self.running:
                self.stop_monitoring()
            
            # Close current connection
            if hasattr(self, 'conn'):
                self.conn.closeConn()
            
            # Update database information
            self.db_name = new_db
            self.db_info = DBS[new_db]
            
            # Create new connection
            self.conn = MdsConn(self.db_name, self.db_info['addr'])
            
            # Update UI
            self.root.title(f"MDSplus Database Monitor - {self.db_name}")
            messagebox.showinfo("Database Switch", f"Switched to database: {self.db_name}")
            
            # Clear table
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Reset status
            self.current_shot = None
            self.previous_shots = []
            self.channels = []
            self.channel_status = {}
            
            # Reset labels
            self.shot_label.config(text="Loading...")
            self.recent_shots_label.config(text="No Records")
            self.update_time_label.config(text="Not Updated")
            self.update_stats()
    
    def monitor_loop(self):
        """Monitoring loop, periodically check database status"""
        while self.running:
            try:
                self.check_current_shot()
                self.update_channel_status()
                self.update_time_label.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            except Exception as e:
                print(f"Monitoring error: {str(e)}")
                self.status_label.config(text=f"Status: Error - {str(e)}")
            
            # Wait for next update
            time.sleep(self.update_interval)
    
    def check_current_shot(self):
        """Check current shot, update if changed"""
        try:
            shot = currentShot(self.db_name, self.db_info['path'])
            if shot and shot != self.current_shot:
                # Update shot list
                if self.current_shot:
                    if self.current_shot not in self.previous_shots:
                        self.previous_shots.insert(0, self.current_shot)
                    # Keep recent shots list length
                    if len(self.previous_shots) > self.max_shots:
                        self.previous_shots = self.previous_shots[:self.max_shots]
                
                self.current_shot = shot
                self.shot_label.config(text=f"{self.current_shot} (New)")
                
                # Update recent shots display
                if self.previous_shots:
                    self.recent_shots_label.config(text=", ".join(map(str, self.previous_shots)))
                
                # Get channel list for new shot
                self.channels = formChaPool(self.db_name, self.current_shot, self.db_info['path'], self.db_info['subtrees'])
                
                # Update table
                self.update_channel_list()
                
                # Log
                print(f"[{datetime.now()}] Found new shot: {self.current_shot}")
            elif self.current_shot:
                self.shot_label.config(text=str(self.current_shot))
        except Exception as e:
            print(f"Shot check error: {str(e)}")
            self.shot_label.config(text="Error")
    
    def update_channel_list(self):
        """Update channel list"""
        # Clear table
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add channels to table
        for channel in self.channels:
            channel_name = channel.strip('\\')
            self.tree.insert("", tk.END, values=(channel_name, "Loading...", "Unknown", "Not Checked"))
    
    def update_channel_status(self):
        """Update status for all channels"""
        if not self.current_shot or not self.channels:
            return
        
        try:
            tree = MdsTree(self.current_shot, self.db_name, self.db_info['path'], self.db_info['subtrees'])
            
            # Reset status counts
            status_counts = {"Has Data": 0, "No Data": 0, "Error": 0}
            
            for item in self.tree.get_children():
                channel_name = self.tree.item(item, "values")[0]
                
                try:
                    # Check if channel has data
                    data_length = tree.isHaveData(channel_name)
                    if data_length > 0:
                        status = "Has Data"
                        status_counts["Has Data"] += 1
                    else:
                        status = "No Data"
                        status_counts["No Data"] += 1
                    
                    # Get update time
                    try:
                        update_time = tree.getWrittenTime(channel_name)
                    except:
                        update_time = "Unknown"
                    
                    # Update table
                    self.tree.item(item, values=(channel_name, status, str(data_length), update_time))
                    
                    # Update status dictionary
                    self.channel_status[channel_name] = {
                        "status": status,
                        "length": data_length,
                        "update_time": update_time
                    }
                except Exception as e:
                    # Update table with error
                    self.tree.item(item, values=(channel_name, "Error", "Unknown", "Unknown"))
                    status_counts["Error"] += 1
            
            tree.close()
            
            # Update statistics
            self.total_label.config(text=f"Total Channels: {len(self.channels)}")
            self.with_data_label.config(text=f"With Data: {status_counts['Has Data']}")
            self.no_data_label.config(text=f"No Data: {status_counts['No Data']}")
            self.error_label.config(text=f"Errors: {status_counts['Error']}")
            
            # Apply filter
            self.filter_channels()
            
        except Exception as e:
            print(f"Channel status update error: {str(e)}")
    
    def filter_channels(self, *args):
        """Filter channel list by search text and filter condition"""
        search_text = self.search_var.get().lower()
        filter_status = self.filter_var.get()
        
        # Status mapping
        status_map = {
            "All": None,
            "Has Data": "Has Data",
            "No Data": "No Data",
            "Error": "Error"
        }
        
        # Show all items
        for item in self.tree.get_children():
            self.tree.detach(item)
        
        # Apply filter
        for item in self.tree.get_children("", False):
            values = self.tree.item(item, "values")
            channel_name = values[0].lower()
            status = values[1]
            
            # Search text filter
            if search_text and search_text not in channel_name:
                continue
            
            # Status filter
            if filter_status != "All" and status != status_map[filter_status]:
                continue
            
            # Show matching items
            self.tree.reattach(item, "", tk.END)
    
    def update_stats(self):
        """Update statistics"""
        if hasattr(self, 'total_label'):
            self.total_label.config(text=f"Total Channels: {len(self.channels)}")
            
            # Calculate counts for each status
            status_counts = {"Has Data": 0, "No Data": 0, "Error": 0}
            for channel, status in self.channel_status.items():
                mapped_status = {
                    "有数据": "Has Data",
                    "无数据": "No Data",
                    "错误": "Error"
                }.get(status["status"], status["status"])
                
                if mapped_status in status_counts:
                    status_counts[mapped_status] += 1
            
            self.with_data_label.config(text=f"With Data: {status_counts['Has Data']}")
            self.no_data_label.config(text=f"No Data: {status_counts['No Data']}")
            self.error_label.config(text=f"Errors: {status_counts['Error']}")
    
    def on_closing(self):
        """Handle window close event"""
        if messagebox.askokcancel("Exit", "Are you sure you want to exit?"):
            self.running = False
            if hasattr(self, 'conn'):
                self.conn.closeConn()
            self.root.destroy()
    
    def run(self):
        """Run the monitor"""
        self.root.mainloop()


def main():
    """Main function, start the monitor"""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="MDSplus Database Monitor")
    parser.add_argument("-d", "--database", default="exl50u", choices=DBS.keys(),
                      help="Database to monitor")
    parser.add_argument("-i", "--interval", type=int, default=5,
                      help="Update interval in seconds")
    parser.add_argument("-m", "--max-shots", type=int, default=10,
                      help="Maximum number of shots to display")
    args = parser.parse_args()
    
    try:
        # Create and run the monitor
        monitor = MDSMonitor(db_name=args.database, update_interval=args.interval, max_shots=args.max_shots)
        print(f"Starting to monitor database {args.database}, update interval {args.interval} seconds")
        monitor.run()
    except Exception as e:
        print(f"Program startup error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 