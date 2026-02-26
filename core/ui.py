import logging
from typing import Optional

try:
    import tkinter as tk
    from tkinter import filedialog, simpledialog, messagebox
except ImportError:
    tk = None

logger = logging.getLogger(__name__)

def get_filepath_from_dialog() -> Optional[str]:
    """
    사용자에게 파일 선택 대화상자를 표시하고, 선택된 파일 경로를 반환합니다.
    """
    if tk is None:
        logger.error("GUI 기능을 사용하려면 Tkinter 패키지가 필요합니다.")
        # Fallback to console input or raise an error
        filepath = input(">> 엑셀 파일의 전체 경로를 입력하세요: ")
        return filepath if filepath else None

    root = tk.Tk()
    root.withdraw()

    try:
        filepath = filedialog.askopenfilename(
            title="점검할 엑셀 파일을 선택하세요",
            filetypes=(("Excel files", "*.xlsx *.xls"), ("All files", "*.*"))
        )
        
        if filepath and not (filepath.endswith('.xlsx') or filepath.endswith('.xls')):
            messagebox.showerror("잘못된 파일 형식", "엑셀 파일(.xlsx, .xls)을 선택해주세요.")
            return None
            
        return filepath if filepath else None
    finally:
        root.destroy()

def get_password_from_dialog() -> Optional[str]:
    """
    사용자에게 암호 입력 대화상자를 표시하고, 입력된 암호를 반환합니다.
    """
    if tk is None:
        logger.error("GUI 기능을 사용하려면 Tkinter 패키지가 필요합니다.")
        password = input(">> 암호화된 파일의 비밀번호를 입력하세요: ")
        return password if password else None
    
    root = tk.Tk()
    root.withdraw()
    
    try:
        password = simpledialog.askstring(
            "암호 입력",
            "파일에 암호가 설정되어 있는 경우, 암호를 입력하세요.",
            show='*'
        )
        return password
    finally:
        root.destroy() 