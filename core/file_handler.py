import pandas as pd
import io
import logging
from openpyxl.styles import PatternFill

try:
    import msoffcrypto
except ImportError:
    msoffcrypto = None

logger = logging.getLogger(__name__)

def read_excel_file(filepath: str, password: str = None) -> pd.DataFrame:
    """
    엑셀 파일을 읽어 데이터프레임으로 반환합니다.
    암호화된 경우 암호를 사용하여 복호화합니다.
    """
    try:
        if password:
            if msoffcrypto is None:
                raise ImportError("암호화된 Excel 파일 지원을 위해 'msoffcrypto-tool' 라이브러리를 설치해주세요.")
            
            decrypted_file = io.BytesIO()
            with open(filepath, 'rb') as f:
                office_file = msoffcrypto.OfficeFile(f)
                office_file.load_key(password=password)
                office_file.decrypt(decrypted_file)
            
            df = pd.read_excel(decrypted_file)
            logger.info(f"암호화된 파일 복호화 성공: {filepath}")
        else:
            df = pd.read_excel(filepath)
            logger.info(f"선택한 파일: {filepath}")
        
        return df
    except Exception as e:
        logger.error(f"엑셀 파일 읽기 실패: {filepath}, 오류: {e}")
        raise

def save_results_to_excel(results: list, output_filepath: str):
    """결과를 엑셀 파일에 저장하고, 실패한 항목에 서식을 적용합니다."""
    try:
        logger.info(f"결과 저장 시작: {output_filepath}")
        
        processed_results = []
        for res in results:
            row = {
                'ip': res.get('ip'),
                'vendor': res.get('vendor'),
                'os': res.get('os'),
                '접속 상태': '성공' if res.get('status') == 'success' else '실패',
                '오류 메시지': res.get('error_message', '')
            }
            if res.get('inspection_results'):
                for key, value in res['inspection_results'].items():
                    if not key.startswith('error_') and key not in ['error', 'backup_error', 'backup_file']:
                        row[key] = value
            
            processed_results.append(row)

        if not processed_results:
            logger.warning("저장할 결과가 없습니다.")
            return

        df = pd.DataFrame(processed_results)
        
        cols = ['ip', 'vendor', 'os', '접속 상태', '오류 메시지']
        other_cols = [col for col in df.columns if col not in cols]
        df = df[cols + other_cols]

        with pd.ExcelWriter(output_filepath, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Inspection Results')
            
            worksheet = writer.sheets['Inspection Results']
            
            light_red_fill = PatternFill(start_color='FFFFC7CE',
                                         end_color='FFFFC7CE',
                                         fill_type='solid')
            
            for idx, row in df.iterrows():
                if row['접속 상태'] == '실패':
                    for col_idx in range(1, len(df.columns) + 1):
                        worksheet.cell(row=idx + 2, column=col_idx).fill = light_red_fill
                        
            for column_cells in worksheet.columns:
                try:
                    length = max(len(str(cell.value)) for cell in column_cells if cell.value)
                    worksheet.column_dimensions[column_cells[0].column_letter].width = length + 2
                except (ValueError, TypeError):
                    pass

        logger.info(f"결과가 저장되었습니다: {output_filepath}")
        
    except Exception as e:
        logger.error(f"결과 저장 중 오류 발생: {str(e)}")
        raise 