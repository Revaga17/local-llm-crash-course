import os
from typing import List, Dict, Optional
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', 'credentials.json')
SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID')
SHEET_NAME = os.getenv('GOOGLE_SHEET_NAME', 'Aset')


class SheetsService:
    def __init__(self):
        self.service = None
        self.sheet_id = SPREADSHEET_ID
        self.sheet_name = SHEET_NAME
        self._init_service()

    def _init_service(self):
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            raise FileNotFoundError(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
        if not self.sheet_id:
            raise ValueError("GOOGLE_SPREADSHEET_ID environment variable not set")

        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        self.service = build('sheets', 'v4', credentials=creds)

    def _get_range(self, range_suffix: str = '') -> str:
        return f"'{self.sheet_name}'!{range_suffix}" if range_suffix else f"'{self.sheet_name}'"

    def ensure_header(self):
        header = ['ID', 'Nama', 'Kategori', 'Lokasi', 'Kondisi', 'Tanggal Beli', 'Harga', 'Catatan']
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=self._get_range('A1:H1')
            ).execute()
            if not result.get('values'):
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=self._get_range('A1:H1'),
                    valueInputOption='RAW',
                    body={'values': [header]}
                ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                self._create_sheet()
                self.ensure_header()
            else:
                raise

    def _create_sheet(self):
        body = {
            'requests': [{
                'addSheet': {
                    'properties': {
                        'title': self.sheet_name,
                        'gridProperties': {'rowCount': 1000, 'columnCount': 8}
                    }
                }
            }]
        }
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id,
            body=body
        ).execute()

    def get_all_assets(self) -> List[Dict]:
        self.ensure_header()
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.sheet_id,
            range=self._get_range('A2:H')
        ).execute()
        rows = result.get('values', [])
        assets = []
        for i, row in enumerate(rows, start=2):
            while len(row) < 8:
                row.append('')
            assets.append({
                'row': i,
                'id': row[0],
                'nama': row[1],
                'kategori': row[2],
                'lokasi': row[3],
                'kondisi': row[4],
                'tanggal_beli': row[5],
                'harga': row[6],
                'catatan': row[7]
            })
        return assets

    def add_asset(self, asset: Dict) -> int:
        self.ensure_header()
        assets = self.get_all_assets()
        new_id = str(max([int(a['id']) for a in assets if a['id'].isdigit()], default=0) + 1)
        row_data = [
            new_id,
            asset.get('nama', ''),
            asset.get('kategori', ''),
            asset.get('lokasi', ''),
            asset.get('kondisi', ''),
            asset.get('tanggal_beli', ''),
            asset.get('harga', ''),
            asset.get('catatan', '')
        ]
        next_row = len(assets) + 2
        self.service.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=self._get_range(f'A{next_row}:H{next_row}'),
            valueInputOption='RAW',
            body={'values': [row_data]}
        ).execute()
        return int(new_id)

    def update_asset(self, row: int, asset: Dict) -> bool:
        row_data = [
            asset.get('id', ''),
            asset.get('nama', ''),
            asset.get('kategori', ''),
            asset.get('lokasi', ''),
            asset.get('kondisi', ''),
            asset.get('tanggal_beli', ''),
            asset.get('harga', ''),
            asset.get('catatan', '')
        ]
        self.service.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=self._get_range(f'A{row}:H{row}'),
            valueInputOption='RAW',
            body={'values': [row_data]}
        ).execute()
        return True

    def delete_asset(self, row: int) -> bool:
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={
                'requests': [{
                    'deleteDimension': {
                        'range': {
                            'sheetId': self._get_sheet_id(),
                            'dimension': 'ROWS',
                            'startIndex': row - 1,
                            'endIndex': row
                        }
                    }
                }]
            }
        ).execute()
        return True

    def _get_sheet_id(self) -> int:
        result = self.service.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
        for sheet in result.get('sheets', []):
            if sheet['properties']['title'] == self.sheet_name:
                return sheet['properties']['sheetId']
        raise ValueError(f"Sheet '{self.sheet_name}' not found")

    def search_assets(self, query: str) -> List[Dict]:
        assets = self.get_all_assets()
        query = query.lower()
        return [a for a in assets if any(query in str(v).lower() for v in a.values() if v != a['row'])]


sheets_service = SheetsService()