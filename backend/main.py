from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import psycopg2
import psycopg2.extras
import os
import uuid
import shutil

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY", "")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "")

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "stroyka"),
    "user": os.getenv("DB_USER", "nikolas"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    return conn

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            client VARCHAR(255),
            status VARCHAR(100),
            budget FLOAT DEFAULT 0,
            deadline VARCHAR(50),
            progress INT DEFAULT 0,
            tasks TEXT[] DEFAULT '{}',
            pricelist_id INT
        );
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            phone VARCHAR(100),
            email VARCHAR(255),
            status VARCHAR(100),
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS materials (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            unit VARCHAR(50),
            quantity FLOAT DEFAULT 0,
            price FLOAT DEFAULT 0,
            min_quantity FLOAT DEFAULT 0,
            project VARCHAR(255),
            category VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS warehouse_history (
            id SERIAL PRIMARY KEY,
            material VARCHAR(255),
            type VARCHAR(50),
            quantity FLOAT,
            date VARCHAR(50),
            project VARCHAR(255),
            issued_to VARCHAR(255),
            issued_by VARCHAR(255),
            date_time VARCHAR(100)
        );
        CREATE TABLE IF NOT EXISTS staff (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            role VARCHAR(100),
            phone VARCHAR(100),
            salary FLOAT DEFAULT 0,
            project VARCHAR(255),
            pay_type VARCHAR(50) DEFAULT 'оклад'
        );
        CREATE TABLE IF NOT EXISTS piecework (
            id SERIAL PRIMARY KEY,
            staff_id VARCHAR(50),
            description VARCHAR(255),
            unit VARCHAR(50),
            quantity FLOAT,
            price_per_unit FLOAT,
            total FLOAT,
            project VARCHAR(255),
            date VARCHAR(50),
            comment TEXT,
            photo_url VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            email VARCHAR(255) UNIQUE,
            password VARCHAR(255),
            role VARCHAR(100)
        );
        CREATE TABLE IF NOT EXISTS pricelists (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            description TEXT,
            for_who VARCHAR(255),
            coefficient FLOAT DEFAULT 1.0
        );
        CREATE TABLE IF NOT EXISTS pricelist_items (
            id SERIAL PRIMARY KEY,
            pricelist_id INT,
            name VARCHAR(255),
            unit VARCHAR(50),
            price FLOAT DEFAULT 0,
            category VARCHAR(255),
            specialization VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS invite_codes (
            id SERIAL PRIMARY KEY,
            code VARCHAR(20) UNIQUE,
            role VARCHAR(100),
            used BOOLEAN DEFAULT FALSE
        );
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            phone VARCHAR(100),
            email VARCHAR(255),
            specialization VARCHAR(255),
            category VARCHAR(255),
            rating FLOAT DEFAULT 5.0,
            status VARCHAR(100)
        );
        CREATE TABLE IF NOT EXISTS supply_requests (
            id SERIAL PRIMARY KEY,
            material_name VARCHAR(255),
            quantity FLOAT,
            unit VARCHAR(50),
            project VARCHAR(255),
            created_by VARCHAR(255),
            date VARCHAR(50),
            status VARCHAR(100) DEFAULT 'Новая',
            notes TEXT,
            selected_suppliers INT[] DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS supplier_offers (
            id SERIAL PRIMARY KEY,
            request_id INT,
            supplier_id INT,
            price_per_unit FLOAT,
            total_price FLOAT,
            delivery_days INT,
            notes TEXT,
            status VARCHAR(100) DEFAULT 'Ожидает'
        );
        CREATE TABLE IF NOT EXISTS supply_history (
            id SERIAL PRIMARY KEY,
            supplier_id INT,
            material_name VARCHAR(255),
            quantity FLOAT,
            unit VARCHAR(50),
            price_per_unit FLOAT,
            total_price FLOAT,
            project VARCHAR(255),
            date VARCHAR(50),
            status VARCHAR(100),
            confirmed_by VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS work_journal (
            id SERIAL PRIMARY KEY,
            master_id INT,
            master_name VARCHAR(255),
            project VARCHAR(255),
            description VARCHAR(255),
            unit VARCHAR(50),
            quantity FLOAT,
            price_per_unit FLOAT,
            total FLOAT,
            date VARCHAR(50),
            status VARCHAR(100) DEFAULT 'На проверке',
            comment TEXT,
            photo_url VARCHAR(255),
            confirmed_by VARCHAR(255),
            confirmed_at VARCHAR(50)
        );
        CREATE TABLE IF NOT EXISTS master_profiles (
            id SERIAL PRIMARY KEY,
            user_id INT UNIQUE,
            full_name VARCHAR(255),
            passport VARCHAR(255),
            inn VARCHAR(50),
            contract_type VARCHAR(50),
            bank_account VARCHAR(255),
            bank_name VARCHAR(255),
            phone VARCHAR(100),
            specialization VARCHAR(255),
            ogrnip VARCHAR(50),
            profile_completed BOOLEAN DEFAULT TRUE
        );
        CREATE TABLE IF NOT EXISTS contracts (
            id SERIAL PRIMARY KEY,
            master_id INT,
            master_name VARCHAR(255),
            contract_type VARCHAR(50),
            contract_number VARCHAR(100),
            project VARCHAR(255),
            start_date VARCHAR(50),
            end_date VARCHAR(50)
        );
        CREATE TABLE IF NOT EXISTS interim_acts (
            id SERIAL PRIMARY KEY,
            master_id INT,
            master_name VARCHAR(255),
            project VARCHAR(255),
            period_start VARCHAR(50),
            period_end VARCHAR(50),
            total_amount FLOAT DEFAULT 0,
            paid_amount FLOAT DEFAULT 0,
            contract_id INT,
            status VARCHAR(100) DEFAULT 'Новый'
        );
        CREATE TABLE IF NOT EXISTS timesheet (
            id SERIAL PRIMARY KEY,
            staff_id INT,
            day VARCHAR(10)
        );
        CREATE TABLE IF NOT EXISTS rooms (
            id SERIAL PRIMARY KEY,
            project VARCHAR(255),
            name VARCHAR(255),
            floor_area FLOAT DEFAULT 0,
            wall_area FLOAT DEFAULT 0,
            ceiling_area FLOAT DEFAULT 0,
            windows INT DEFAULT 0,
            doors INT DEFAULT 0,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS room_works (
            id SERIAL PRIMARY KEY,
            room_id INT,
            project VARCHAR(255),
            room_name VARCHAR(255),
            master_id INT,
            master_name VARCHAR(255),
            description VARCHAR(255),
            surface VARCHAR(100),
            unit VARCHAR(50),
            quantity FLOAT,
            price_per_unit FLOAT DEFAULT 0,
            total FLOAT DEFAULT 0,
            date VARCHAR(50),
            status VARCHAR(100) DEFAULT 'На проверке',
            photo_url VARCHAR(255),
            confirmed_by VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS tools (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            inventory_number VARCHAR(100),
            cost FLOAT DEFAULT 0,
            status VARCHAR(100) DEFAULT 'На складе',
            location VARCHAR(100) DEFAULT 'Основной склад',
            project VARCHAR(255),
            master_id INT,
            master_name VARCHAR(255),
            issue_type VARCHAR(100),
            photo_url VARCHAR(255),
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS tool_history (
            id SERIAL PRIMARY KEY,
            tool_id INT,
            tool_name VARCHAR(255),
            action VARCHAR(100),
            from_location VARCHAR(255),
            to_location VARCHAR(255),
            master_name VARCHAR(255),
            project VARCHAR(255),
            issue_type VARCHAR(100),
            condition VARCHAR(100),
            date VARCHAR(50),
            created_by VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS warehouse_main (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            unit VARCHAR(50),
            quantity FLOAT DEFAULT 0,
            price FLOAT DEFAULT 0,
            min_quantity FLOAT DEFAULT 0,
            category VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS warehouse_movements (
            id SERIAL PRIMARY KEY,
            material_name VARCHAR(255),
            from_location VARCHAR(255),
            to_location VARCHAR(255),
            quantity FLOAT,
            unit VARCHAR(50),
            date VARCHAR(50),
            created_by VARCHAR(255),
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS inventory (
            id SERIAL PRIMARY KEY,
            project VARCHAR(255),
            date VARCHAR(50),
            created_by VARCHAR(255),
            status VARCHAR(100) DEFAULT 'Открыта',
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS inventory_items (
            id SERIAL PRIMARY KEY,
            inventory_id INT,
            material_name VARCHAR(255),
            unit VARCHAR(50),
            expected FLOAT,
            actual FLOAT,
            difference FLOAT,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS pd_consents (
            id SERIAL PRIMARY KEY,
            user_id INT UNIQUE,
            signed_at VARCHAR(100),
            scan_url VARCHAR(255),
            uploaded_by VARCHAR(255)
        );
        CREATE TABLE IF NOT EXISTS project_ai_summary (
            project_name VARCHAR(255) PRIMARY KEY,
            payload_hash VARCHAR(64),
            summary TEXT,
            updated_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE work_journal ADD COLUMN IF NOT EXISTS materials_used TEXT;
        ALTER TABLE estimates ADD COLUMN IF NOT EXISTS is_template BOOLEAN DEFAULT FALSE;
        CREATE TABLE IF NOT EXISTS estimate_versions (
            id SERIAL PRIMARY KEY,
            estimate_id INT NOT NULL,
            version_label VARCHAR(100),
            sections_json TEXT,
            total NUMERIC(14,2) DEFAULT 0,
            comment TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS estimate_chat_messages (
            id SERIAL PRIMARY KEY,
            estimate_id INT NOT NULL,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        ALTER TABLE brigade_contracts ADD COLUMN IF NOT EXISTS pricelist_id INT;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS last_name VARCHAR(100);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS first_name VARCHAR(100);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS middle_name VARCHAR(100);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS birth_date DATE;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS citizenship VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS address TEXT;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS photo_url VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS email_work VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS email_personal VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS phone_extra VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS passport_series VARCHAR(10);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS passport_number VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS passport_issued_by VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS passport_issued_date DATE;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS inn VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS snils VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS specialization VARCHAR(100);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS category VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS employment_type VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS hired_date DATE;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS fired_date DATE;
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS status VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS brigade VARCHAR(100);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS bank_account VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS bank_name VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS bank_bik VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS bank_corr VARCHAR(50);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS ogrnip VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS card_number VARCHAR(20);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS signature_url VARCHAR(255);
        ALTER TABLE staff ADD COLUMN IF NOT EXISTS notes TEXT;
        ALTER TABLE pricelist_items ADD COLUMN IF NOT EXISTS item_type VARCHAR(20);
        CREATE TABLE IF NOT EXISTS staff_documents (
            id SERIAL PRIMARY KEY,
            staff_id INT NOT NULL,
            doc_type VARCHAR(50) NOT NULL,
            title VARCHAR(255),
            file_url VARCHAR(500),
            status VARCHAR(50) DEFAULT 'действует',
            signed_at DATE,
            expires_at DATE,
            notes TEXT,
            created_by VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        INSERT INTO users (name, email, password, role)
        VALUES
            ('Директор', 'admin@stroyka.ru', 'admin123', 'директор'),
            ('Бухгалтер', 'buh@stroyka.ru', 'buh123', 'бухгалтер'),
            ('Прораб', 'prorab@stroyka.ru', 'prorab123', 'прораб'),
            ('Мастер', 'master@stroyka.ru', 'master123', 'мастер')
        ON CONFLICT (email) DO NOTHING;
    """)
    conn.close()

init_db()
class ProjectModel(BaseModel):
    name: str
    client: str = ""
    status: str = "Планирование"
    budget: float = 0
    deadline: str = ""
    progress: int = 0
    tasks: List[str] = []
    pricelistId: Optional[int] = None
    floors: int = 1
    liters: str = ""

class ClientModel(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    status: str = "Активный"
    notes: str = ""

class MaterialModel(BaseModel):
    name: str
    unit: str = "шт"
    quantity: float = 0
    price: float = 0
    minQuantity: float = 0
    project: str = ""
    category: str = ""

class WarehouseMainModel(BaseModel):
    name: str
    unit: str = "шт"
    quantity: float = 0
    price: float = 0
    minQuantity: float = 0
    category: str = ""

class WarehouseHistoryModel(BaseModel):
    material: str
    type: str
    quantity: float
    date: str
    project: str = ""
    issuedTo: str = ""
    issuedBy: str = ""
    dateTime: str = ""

class WarehouseMovementModel(BaseModel):
    materialName: str
    fromLocation: str
    toLocation: str
    quantity: float
    unit: str = ""
    date: str = ""
    createdBy: str = ""
    notes: str = ""

class StaffModel(BaseModel):
    name: str
    role: str = ""
    phone: str = ""
    salary: float = 0
    project: str = ""
    payType: str = "оклад"
    lastName: Optional[str] = ""
    firstName: Optional[str] = ""
    middleName: Optional[str] = ""
    birthDate: Optional[str] = ""
    citizenship: Optional[str] = ""
    address: Optional[str] = ""
    photoUrl: Optional[str] = ""
    emailWork: Optional[str] = ""
    emailPersonal: Optional[str] = ""
    phoneExtra: Optional[str] = ""
    passportSeries: Optional[str] = ""
    passportNumber: Optional[str] = ""
    passportIssuedBy: Optional[str] = ""
    passportIssuedDate: Optional[str] = ""
    inn: Optional[str] = ""
    snils: Optional[str] = ""
    specialization: Optional[str] = ""
    category: Optional[str] = ""
    employmentType: Optional[str] = ""
    hiredDate: Optional[str] = ""
    firedDate: Optional[str] = ""
    status: Optional[str] = "Активен"
    brigade: Optional[str] = ""
    bankAccount: Optional[str] = ""
    bankName: Optional[str] = ""
    bankBik: Optional[str] = ""
    bankCorr: Optional[str] = ""
    ogrnip: Optional[str] = ""
    cardNumber: Optional[str] = ""
    signatureUrl: Optional[str] = ""
    notes: Optional[str] = ""

class PieceworkModel(BaseModel):
    staffId: str
    description: str
    unit: str = "м2"
    quantity: float
    pricePerUnit: float
    total: float
    project: str = ""
    date: str = ""
    comment: str = ""
    photoUrl: str = ""

class UserModel(BaseModel):
    name: str
    email: str
    password: str = ""
    role: str = "прораб"
    projectId: str = ""
    projectName: str = ""

class LoginModel(BaseModel):
    email: str
    password: str

class PricelistModel(BaseModel):
    name: str
    description: str = ""
    forWho: str = ""
    coefficient: float = 1.0

class PricelistItemModel(BaseModel):
    pricelistId: int
    name: str
    unit: str = "м2"
    price: float = 0
    category: str = ""
    specialization: str = ""

class InviteCodeModel(BaseModel):
    role: str

class RegisterModel(BaseModel):
    name: str
    email: str
    password: str
    code: str

class SupplierModel(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    specialization: str = ""
    category: str = ""
    rating: float = 5.0
    status: str = "Активный"

class SupplyRequestModel(BaseModel):
    materialName: str
    quantity: float
    unit: str = "шт"
    project: str = ""
    createdBy: str = ""
    date: str = ""
    notes: str = ""
    selectedSuppliers: List[int] = []

class SupplierOfferModel(BaseModel):
    requestId: int
    supplierId: int
    pricePerUnit: float
    totalPrice: float
    deliveryDays: int = 0
    notes: str = ""

class SupplyHistoryModel(BaseModel):
    supplierId: int
    materialName: str
    quantity: float
    unit: str = ""
    pricePerUnit: float
    totalPrice: float
    project: str = ""
    date: str = ""
    status: str = "Ожидает поставки"

class WorkJournalModel(BaseModel):
    masterId: int
    masterName: str
    project: str
    description: str
    unit: str
    quantity: float
    pricePerUnit: float = 0
    total: float = 0
    date: str
    comment: str = ""
    photoUrl: str = ""
    materialsUsed: list = []

class MasterProfileModel(BaseModel):
    userId: int
    fullName: str
    passport: str = ""
    inn: str = ""
    contractType: str = "ГПХ"
    bankAccount: str = ""
    bankName: str = ""
    phone: str = ""
    specialization: str = ""
    ogrnip: str = ""

class ContractModel(BaseModel):
    masterId: int
    masterName: str
    contractType: str = "ГПХ"
    contractNumber: str
    project: str
    startDate: str = ""
    endDate: str = ""

class InterimActModel(BaseModel):
    masterId: int
    masterName: str
    project: str
    periodStart: str
    periodEnd: str
    totalAmount: float = 0
    paidAmount: float = 0
    contractId: Optional[int] = None

class TimesheetModel(BaseModel):
    staffId: int
    day: str

class CopyPricelistModel(BaseModel):
    name: str

class RoomModel(BaseModel):
    floor: int = 1
    liter: str = ''
    roomType: str = 'Комната'
    project: str
    name: str
    floorArea: float = 0
    wallArea: float = 0
    ceilingArea: float = 0
    windows: int = 0
    doors: int = 0
    notes: str = ""

class RoomWorkModel(BaseModel):
    roomId: int
    project: str
    roomName: str
    masterId: int
    masterName: str
    description: str
    surface: str = ""
    unit: str = "м2"
    quantity: float = 0
    pricePerUnit: float = 0
    total: float = 0
    date: str = ""
    photoUrl: str = ""

class ToolModel(BaseModel):
    name: str
    inventoryNumber: str = ""
    cost: float = 0
    status: str = "На складе"
    location: str = "Основной склад"
    project: str = ""
    masterId: Optional[int] = None
    masterName: str = ""
    issueType: str = ""
    photoUrl: str = ""
    notes: str = ""

class ToolHistoryModel(BaseModel):
    toolId: int
    toolName: str
    action: str
    fromLocation: str = ""
    toLocation: str = ""
    masterName: str = ""
    project: str = ""
    issueType: str = ""
    condition: str = ""
    date: str = ""
    createdBy: str = ""

class InventoryModel(BaseModel):
    project: str
    date: str
    createdBy: str
    notes: str = ""

class InventoryItemModel(BaseModel):
    inventoryId: int
    materialName: str
    unit: str
    expected: float
    actual: float
    difference: float
    notes: str = ""

class PdConsentModel(BaseModel):
    userId: int
    signedAt: str = ""
    scanUrl: str = ""
    uploadedBy: str = ""

@app.post("/login")
def login(data: LoginModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE email=%s AND password=%s", (data.email, data.password))
    user = cur.fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    return dict(user)

@app.post("/register")
def register(data: RegisterModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM invite_codes WHERE code=%s AND used=FALSE", (data.code,))
    invite = cur.fetchone()
    if not invite:
        conn.close()
        raise HTTPException(status_code=400, detail="Неверный или использованный код")
    try:
        cur.execute("INSERT INTO users (name,email,password,role) VALUES (%s,%s,%s,%s) RETURNING *",
                    (data.name, data.email, data.password, invite['role']))
        user = cur.fetchone()
        cur.execute("UPDATE invite_codes SET used=TRUE WHERE code=%s", (data.code,))
        conn.close()
        return dict(user)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/projects")
def get_projects():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,name,client,status,budget,deadline,progress,tasks,pricelist_id as \"pricelistId\",floors,liters FROM projects")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/projects")
def create_project(p: ProjectModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO projects (name,client,status,budget,deadline,progress,tasks,pricelist_id,floors,liters) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,name,client,status,budget,deadline,progress,tasks,pricelist_id as \"pricelistId\",floors,liters",
                (p.name,p.client,p.status,p.budget,p.deadline,p.progress,p.tasks,p.pricelistId))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/projects/{id}")
def update_project(id: int, p: ProjectModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE projects SET name=%s,client=%s,status=%s,budget=%s,deadline=%s,progress=%s,tasks=%s,pricelist_id=%s,floors=%s,liters=%s WHERE id=%s",
                (p.name,p.client,p.status,p.budget,p.deadline,p.progress,p.tasks,p.pricelistId,id))
    conn.close()
    return {"ok": True}

@app.delete("/projects/{id}")
def delete_project(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM projects WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/clients")
def get_clients():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM clients")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/clients")
def create_client(c: ClientModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO clients (name,phone,email,status,notes) VALUES (%s,%s,%s,%s,%s) RETURNING *",
                (c.name,c.phone,c.email,c.status,c.notes))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/clients/{id}")
def update_client(id: int, c: ClientModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE clients SET name=%s,phone=%s,email=%s,status=%s,notes=%s WHERE id=%s",
                (c.name,c.phone,c.email,c.status,c.notes,id))
    conn.close()
    return {"ok": True}

@app.delete("/clients/{id}")
def delete_client(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM clients WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/materials")
def get_materials():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,name,unit,quantity,price,min_quantity as \"minQuantity\",project,category FROM materials")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/materials")
def create_material(m: MaterialModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO materials (name,unit,quantity,price,min_quantity,project,category) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id,name,unit,quantity,price,min_quantity as \"minQuantity\",project,category",
                (m.name,m.unit,m.quantity,m.price,m.minQuantity,m.project,m.category))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/materials/{id}")
def update_material(id: int, m: MaterialModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE materials SET name=%s,unit=%s,quantity=%s,price=%s,min_quantity=%s,project=%s,category=%s WHERE id=%s",
                (m.name,m.unit,m.quantity,m.price,m.minQuantity,m.project,m.category,id))
    conn.close()
    return {"ok": True}

@app.delete("/materials/{id}")
def delete_material(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM materials WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/warehouse-main")
def get_warehouse_main():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,name,unit,quantity,price,min_quantity as \"minQuantity\",category FROM warehouse_main")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/warehouse-main")
def create_warehouse_main(m: WarehouseMainModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO warehouse_main (name,unit,quantity,price,min_quantity,category) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,name,unit,quantity,price,min_quantity as \"minQuantity\",category",
                (m.name,m.unit,m.quantity,m.price,m.minQuantity,m.category))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/warehouse-main/{id}")
def update_warehouse_main(id: int, m: WarehouseMainModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE warehouse_main SET name=%s,unit=%s,quantity=%s,price=%s,min_quantity=%s,category=%s WHERE id=%s",
                (m.name,m.unit,m.quantity,m.price,m.minQuantity,m.category,id))
    conn.close()
    return {"ok": True}

@app.delete("/warehouse-main/{id}")
def delete_warehouse_main(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM warehouse_main WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/warehouse-movements")
def get_warehouse_movements():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,material_name as \"materialName\",from_location as \"fromLocation\",to_location as \"toLocation\",quantity,unit,date,created_by as \"createdBy\",notes FROM warehouse_movements ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/warehouse-movements")
def create_warehouse_movement(m: WarehouseMovementModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO warehouse_movements (material_name,from_location,to_location,quantity,unit,date,created_by,notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (m.materialName,m.fromLocation,m.toLocation,m.quantity,m.unit,m.date,m.createdBy,m.notes))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.get("/warehouse-history")
def get_warehouse_history():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,material,type,quantity,date,project,issued_to as \"issuedTo\",issued_by as \"issuedBy\",date_time as \"dateTime\" FROM warehouse_history ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/warehouse-history")
def create_warehouse_history(h: WarehouseHistoryModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO warehouse_history (material,type,quantity,date,project,issued_to,issued_by,date_time) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (h.material,h.type,h.quantity,h.date,h.project,h.issuedTo,h.issuedBy,h.dateTime))
    row = cur.fetchone()
    conn.close()
    return dict(row)

STAFF_COLUMNS = """id, name, role, phone, salary, project, pay_type as "payType",
    last_name as "lastName", first_name as "firstName", middle_name as "middleName",
    birth_date as "birthDate", citizenship, address, photo_url as "photoUrl",
    email_work as "emailWork", email_personal as "emailPersonal", phone_extra as "phoneExtra",
    passport_series as "passportSeries", passport_number as "passportNumber",
    passport_issued_by as "passportIssuedBy", passport_issued_date as "passportIssuedDate",
    inn, snils, specialization, category,
    employment_type as "employmentType", hired_date as "hiredDate", fired_date as "firedDate",
    status, brigade, bank_account as "bankAccount", bank_name as "bankName",
    bank_bik as "bankBik", bank_corr as "bankCorr", ogrnip, card_number as "cardNumber",
    signature_url as "signatureUrl", notes"""

def _staff_tuple(s):
    def d(v):
        return v if v else None
    return (s.name, s.role, s.phone, s.salary, s.project, s.payType,
            s.lastName or None, s.firstName or None, s.middleName or None,
            d(s.birthDate), s.citizenship or None, s.address or None, s.photoUrl or None,
            s.emailWork or None, s.emailPersonal or None, s.phoneExtra or None,
            s.passportSeries or None, s.passportNumber or None,
            s.passportIssuedBy or None, d(s.passportIssuedDate),
            s.inn or None, s.snils or None, s.specialization or None, s.category or None,
            s.employmentType or None, d(s.hiredDate), d(s.firedDate),
            s.status or "Активен", s.brigade or None,
            s.bankAccount or None, s.bankName or None, s.bankBik or None, s.bankCorr or None,
            s.ogrnip or None, s.cardNumber or None, s.signatureUrl or None, s.notes or None)

STAFF_INSERT_COLS = """name, role, phone, salary, project, pay_type,
    last_name, first_name, middle_name, birth_date, citizenship, address, photo_url,
    email_work, email_personal, phone_extra,
    passport_series, passport_number, passport_issued_by, passport_issued_date,
    inn, snils, specialization, category,
    employment_type, hired_date, fired_date, status, brigade,
    bank_account, bank_name, bank_bik, bank_corr, ogrnip, card_number,
    signature_url, notes"""
STAFF_PLACEHOLDERS = ",".join(["%s"] * 37)

@app.get("/staff")
def get_staff():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT " + STAFF_COLUMNS + " FROM staff ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        for k in ("birthDate", "passportIssuedDate", "hiredDate", "firedDate"):
            d[k] = str(d[k]) if d.get(k) else ""
        for k in list(d.keys()):
            if d[k] is None:
                d[k] = ""
        result.append(d)
    return result

@app.post("/staff")
def create_staff(s: StaffModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO staff (" + STAFF_INSERT_COLS + ") VALUES (" + STAFF_PLACEHOLDERS + ") RETURNING id", _staff_tuple(s))
    new_id = cur.fetchone()[0]
    conn.commit(); conn.close()
    return {"id": new_id, "ok": True}

@app.put("/staff/{id}")
def update_staff(id: int, s: StaffModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""UPDATE staff SET name=%s, role=%s, phone=%s, salary=%s, project=%s, pay_type=%s,
        last_name=%s, first_name=%s, middle_name=%s, birth_date=%s, citizenship=%s, address=%s, photo_url=%s,
        email_work=%s, email_personal=%s, phone_extra=%s,
        passport_series=%s, passport_number=%s, passport_issued_by=%s, passport_issued_date=%s,
        inn=%s, snils=%s, specialization=%s, category=%s,
        employment_type=%s, hired_date=%s, fired_date=%s, status=%s, brigade=%s,
        bank_account=%s, bank_name=%s, bank_bik=%s, bank_corr=%s, ogrnip=%s, card_number=%s,
        signature_url=%s, notes=%s WHERE id=%s""", _staff_tuple(s) + (id,))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/staff/{id}")
def delete_staff(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM staff WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/staff/{staff_id}/profile")
def get_staff_profile(staff_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM staff WHERE id=%s", (staff_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    staff_name = row[1] or ""

    cur.execute("SELECT id, doc_type, title, file_url, status, signed_at, expires_at, notes, created_at FROM staff_documents WHERE staff_id=%s ORDER BY id DESC", (staff_id,))
    custom = [{"id": r[0], "docType": r[1], "title": r[2] or "", "fileUrl": r[3] or "", "status": r[4] or "", "signedAt": str(r[5]) if r[5] else "", "expiresAt": str(r[6]) if r[6] else "", "notes": r[7] or "", "createdAt": str(r[8])} for r in cur.fetchall()]

    # Match user by name (legacy linkage)
    cur.execute("SELECT id FROM users WHERE name=%s LIMIT 1", (staff_name,))
    u = cur.fetchone()
    user_id = u[0] if u else None

    contracts_list = []
    if user_id is not None:
        cur.execute("SELECT id, contract_number, project, start_date, end_date, signed_at, status FROM contracts WHERE master_id=%s ORDER BY id DESC", (user_id,))
        for r in cur.fetchall():
            contracts_list.append({"id": r[0], "contractNumber": r[1] or "", "project": r[2] or "", "startDate": str(r[3]) if r[3] else "", "endDate": str(r[4]) if r[4] else "", "signedAt": str(r[5]) if r[5] else "", "status": r[6] or ""})

    acts_list = []
    if user_id is not None:
        cur.execute("SELECT id, act_number, project, period_from, period_to, total_amount, paid_amount, status, created_at FROM interim_acts WHERE master_id=%s ORDER BY id DESC", (user_id,))
        for r in cur.fetchall():
            acts_list.append({"id": r[0], "actNumber": r[1] or "", "project": r[2] or "", "periodFrom": str(r[3]) if r[3] else "", "periodTo": str(r[4]) if r[4] else "", "totalAmount": float(r[5] or 0), "paidAmount": float(r[6] or 0), "status": r[7] or "", "createdAt": str(r[8])})

    pd_consents = []
    if user_id is not None:
        cur.execute("SELECT id, signed_at, scan_url, uploaded_by FROM pd_consents WHERE user_id=%s ORDER BY id DESC", (user_id,))
        for r in cur.fetchall():
            pd_consents.append({"id": r[0], "signedAt": r[1] or "", "scanUrl": r[2] or "", "uploadedBy": r[3] or ""})

    tb_entries = []
    cur.execute("SELECT id, project_name, instructor, instruction_type, date FROM tb_journal WHERE master_name=%s ORDER BY id DESC LIMIT 20", (staff_name,))
    for r in cur.fetchall():
        tb_entries.append({"id": r[0], "projectName": r[1] or "", "instructor": r[2] or "", "instructionType": r[3] or "", "date": str(r[4]) if r[4] else ""})

    works = []
    cur.execute("SELECT project, description, quantity, unit, total, date, status FROM work_journal WHERE master_name=%s ORDER BY id DESC LIMIT 50", (staff_name,))
    for r in cur.fetchall():
        works.append({"project": r[0] or "", "description": r[1] or "", "quantity": float(r[2] or 0), "unit": r[3] or "", "total": float(r[4] or 0), "date": str(r[5]) if r[5] else "", "status": r[6] or ""})

    cur.close(); conn.close()
    return {
        "staffId": staff_id,
        "staffName": staff_name,
        "userId": user_id,
        "customDocuments": custom,
        "contracts": contracts_list,
        "acts": acts_list,
        "pdConsents": pd_consents,
        "tbJournal": tb_entries,
        "workJournal": works,
    }

@app.post("/staff/{staff_id}/documents")
def add_staff_document(staff_id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO staff_documents (staff_id, doc_type, title, file_url, status, signed_at, expires_at, notes, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (staff_id, data.get("docType","другое"), data.get("title",""), data.get("fileUrl","") or None,
         data.get("status","действует"), data.get("signedAt") or None, data.get("expiresAt") or None,
         data.get("notes",""), data.get("createdBy","")))
    new_id = cur.fetchone()[0]
    conn.commit(); cur.close(); conn.close()
    return {"id": new_id, "ok": True}

@app.delete("/staff-documents/{doc_id}")
def delete_staff_document(doc_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM staff_documents WHERE id=%s", (doc_id,))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}

@app.get("/piecework")
def get_piecework():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,staff_id as \"staffId\",description,unit,quantity,price_per_unit as \"pricePerUnit\",total,project,date,comment,photo_url as \"photoUrl\" FROM piecework ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/piecework")
def create_piecework(p: PieceworkModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO piecework (staff_id,description,unit,quantity,price_per_unit,total,project,date,comment,photo_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (p.staffId,p.description,p.unit,p.quantity,p.pricePerUnit,p.total,p.project,p.date,p.comment,p.photoUrl))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.delete("/piecework/{id}")
def delete_piecework(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM piecework WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/users")
def get_users():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,name,email,role FROM users")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/users")
def create_user(u: UserModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("INSERT INTO users (name,email,password,role,project_id,project_name) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,name,email,role,project_id,project_name",
                    (u.name,u.email,u.password,u.role,int(u.projectId) if u.projectId else None,u.projectName or ""))
        row = cur.fetchone()
        conn.close()
        return dict(row)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/users/{id}")
def update_user(id: int, u: UserModel):
    conn = get_db()
    cur = conn.cursor()
    if u.password:
        cur.execute("UPDATE users SET name=%s,email=%s,password=%s,role=%s WHERE id=%s",
                    (u.name,u.email,u.password,u.role,id))
    else:
        cur.execute("UPDATE users SET name=%s,email=%s,role=%s WHERE id=%s",
                    (u.name,u.email,u.role,id))
    conn.close()
    return {"ok": True}

@app.delete("/users/{id}")
def delete_user(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/pricelists")
def get_pricelists():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,name,description,for_who as \"forWho\",coefficient FROM pricelists")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/pricelists")
def create_pricelist(p: PricelistModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO pricelists (name,description,for_who,coefficient) VALUES (%s,%s,%s,%s) RETURNING id,name,description,for_who as \"forWho\",coefficient",
                (p.name,p.description,p.forWho,p.coefficient))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/pricelists/{id}")
def update_pricelist(id: int, p: PricelistModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE pricelists SET name=%s,description=%s,for_who=%s,coefficient=%s WHERE id=%s",
                (p.name,p.description,p.forWho,p.coefficient,id))
    conn.close()
    return {"ok": True}

@app.delete("/pricelists/{id}")
def delete_pricelist(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM pricelists WHERE id=%s", (id,))
    cur.execute("DELETE FROM pricelist_items WHERE pricelist_id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.post("/pricelists/{id}/copy")
def copy_pricelist(id: int, data: CopyPricelistModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM pricelists WHERE id=%s", (id,))
    pl = cur.fetchone()
    cur.execute("INSERT INTO pricelists (name,description,for_who,coefficient) VALUES (%s,%s,%s,%s) RETURNING *",
                (data.name,pl['description'],pl['for_who'],pl['coefficient']))
    new_pl = cur.fetchone()
    cur.execute("SELECT * FROM pricelist_items WHERE pricelist_id=%s", (id,))
    items = cur.fetchall()
    for item in items:
        cur.execute("INSERT INTO pricelist_items (pricelist_id,name,unit,price,category,specialization) VALUES (%s,%s,%s,%s,%s,%s)",
                    (new_pl['id'],item['name'],item['unit'],item['price'],item['category'],item['specialization']))
    conn.close()
    return dict(new_pl)

@app.get("/pricelists/{id}/items")
def get_pricelist_items(id: int):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,pricelist_id as \"pricelistId\",name,unit,price,category,specialization FROM pricelist_items WHERE pricelist_id=%s ORDER BY category,name", (id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/pricelist-items")
def create_pricelist_item(item: PricelistItemModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO pricelist_items (pricelist_id,name,unit,price,category,specialization) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,pricelist_id as \"pricelistId\",name,unit,price,category,specialization",
                (item.pricelistId,item.name,item.unit,item.price,item.category,item.specialization))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/pricelist-items/{id}")
def update_pricelist_item(id: int, item: PricelistItemModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE pricelist_items SET name=%s,unit=%s,price=%s,category=%s,specialization=%s WHERE id=%s",
                (item.name,item.unit,item.price,item.category,item.specialization,id))
    conn.close()
    return {"ok": True}

@app.delete("/pricelist-items/{id}")
def delete_pricelist_item(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM pricelist_items WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/invite-codes")
def get_invite_codes():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM invite_codes ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/invite-codes")
def create_invite_code(data: InviteCodeModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    code = str(uuid.uuid4())[:8].upper()
    cur.execute("INSERT INTO invite_codes (code,role) VALUES (%s,%s) RETURNING *", (code,data.role))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.delete("/invite-codes/{id}")
def delete_invite_code(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM invite_codes WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/suppliers")
def get_suppliers():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM suppliers ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/suppliers")
def create_supplier(s: SupplierModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO suppliers (name,phone,email,specialization,category,rating,status) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (s.name,s.phone,s.email,s.specialization,s.category,s.rating,s.status))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/suppliers/{id}")
def update_supplier(id: int, s: SupplierModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE suppliers SET name=%s,phone=%s,email=%s,specialization=%s,category=%s,rating=%s,status=%s WHERE id=%s",
                (s.name,s.phone,s.email,s.specialization,s.category,s.rating,s.status,id))
    conn.close()
    return {"ok": True}

@app.delete("/suppliers/{id}")
def delete_supplier(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM suppliers WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/supply-requests")
def get_supply_requests():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,material_name as \"materialName\",quantity,unit,project,created_by as \"createdBy\",date,status,notes,selected_suppliers as \"selectedSuppliers\" FROM supply_requests ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/supply-requests")
def create_supply_request(r: SupplyRequestModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO supply_requests (material_name,quantity,unit,project,created_by,date,notes,selected_suppliers) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,material_name as \"materialName\",quantity,unit,project,created_by as \"createdBy\",date,status,notes,selected_suppliers as \"selectedSuppliers\"",
                (r.materialName,r.quantity,r.unit,r.project,r.createdBy,r.date,r.notes,r.selectedSuppliers))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/supply-requests/{id}")
def update_supply_request(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    if 'status' in data:
        cur.execute("UPDATE supply_requests SET status=%s WHERE id=%s", (data['status'],id))
    conn.close()
    return {"ok": True}

@app.get("/supplier-offers")
def get_supplier_offers():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,request_id as \"requestId\",supplier_id as \"supplierId\",price_per_unit as \"pricePerUnit\",total_price as \"totalPrice\",delivery_days as \"deliveryDays\",notes,status,delivery_status as \"deliveryStatus\" FROM supplier_offers")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/supplier-offers")
def create_supplier_offer(o: SupplierOfferModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO supplier_offers (request_id,supplier_id,price_per_unit,total_price,delivery_days,notes) VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
                (o.requestId,o.supplierId,o.pricePerUnit,o.totalPrice,o.deliveryDays,o.notes))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/supplier-offers/{id}")
def update_supplier_offer(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    if 'status' in data:
        cur.execute("UPDATE supplier_offers SET status=%s WHERE id=%s", (data['status'],id))
    if 'deliveryStatus' in data:
        cur.execute("UPDATE supplier_offers SET delivery_status=%s WHERE id=%s", (data['deliveryStatus'],id))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.get("/supply-history")
def get_supply_history():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,supplier_id as \"supplierId\",material_name as \"materialName\",quantity,unit,price_per_unit as \"pricePerUnit\",total_price as \"totalPrice\",project,date,status,confirmed_by as \"confirmedBy\" FROM supply_history ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/supply-history")
def create_supply_history(d: SupplyHistoryModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO supply_history (supplier_id,material_name,quantity,unit,price_per_unit,total_price,project,date,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (d.supplierId,d.materialName,d.quantity,d.unit,d.pricePerUnit,d.totalPrice,d.project,d.date,d.status))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/supply-history/{id}")
def update_supply_history(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    status = data.get('status','')
    confirmed_by = data.get('confirmedBy','')
    cur.execute("UPDATE supply_history SET status=%s,confirmed_by=%s WHERE id=%s", (status,confirmed_by,id))
    conn.close()
    return {"ok": True}

@app.get("/work-journal")
def get_work_journal():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,master_id as \"masterId\",master_name as \"masterName\",project,description,unit,quantity,price_per_unit as \"pricePerUnit\",total,date,status,comment,photo_url as \"photoUrl\",confirmed_by as \"confirmedBy\",confirmed_at as \"confirmedAt\",materials_used as \"materialsUsed\" FROM work_journal ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/work-journal")
def create_work_journal(w: WorkJournalModel):
    used = [m for m in (w.materialsUsed or []) if m.get("name") and float(m.get("quantity") or 0) > 0]

    conn = get_db()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        for m in used:
            name = m["name"]
            qty = float(m["quantity"])
            cur.execute("SELECT id, quantity FROM materials WHERE name=%s AND project=%s FOR UPDATE", (name, w.project))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=400, detail="Материал «"+name+"» не найден на складе объекта «"+w.project+"»")
            stock_qty = float(row["quantity"] or 0)
            if stock_qty < qty:
                raise HTTPException(status_code=400, detail="На складе «"+w.project+"» только "+str(stock_qty)+" "+(m.get("unit") or "")+" «"+name+"», запрошено "+str(qty))
            cur.execute("UPDATE materials SET quantity=quantity-%s WHERE id=%s", (qty, row["id"]))
            cur.execute("INSERT INTO warehouse_history (material,type,quantity,date,project,issued_by,date_time) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (name, "расход (работа)", qty, w.date or None, w.project, w.masterName or "", __import__("datetime").datetime.now().strftime("%d.%m.%Y, %H:%M")))

        import json as _json
        materials_json = _json.dumps(used, ensure_ascii=False) if used else None
        cur.execute("INSERT INTO work_journal (master_id,master_name,project,description,unit,quantity,price_per_unit,total,date,comment,photo_url,materials_used) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                    (w.masterId,w.masterName,w.project,w.description,w.unit,w.quantity,w.pricePerUnit,w.total,w.date,w.comment,w.photoUrl,materials_json))
        row = cur.fetchone()
        conn.commit()
        return dict(row)
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.put("/work-journal/{id}")
def update_work_journal(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    status = data.get('status','')
    confirmed_by = data.get('confirmedBy','')
    confirmed_at = data.get('confirmedAt','')
    comment = data.get('comment','')
    cur.execute("UPDATE work_journal SET status=%s,confirmed_by=%s,confirmed_at=%s,comment=%s WHERE id=%s",
                (status,confirmed_by,confirmed_at,comment,id))
    conn.close()
    return {"ok": True}

@app.get("/master-profiles")
def get_master_profiles():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,user_id as \"userId\",full_name as \"fullName\",passport,inn,contract_type as \"contractType\",bank_account as \"bankAccount\",bank_name as \"bankName\",phone,specialization,ogrnip,profile_completed as \"profileCompleted\" FROM master_profiles")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/master-profile/{user_id}")
def get_master_profile(user_id: int):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,user_id as \"userId\",full_name as \"fullName\",passport,inn,contract_type as \"contractType\",bank_account as \"bankAccount\",bank_name as \"bankName\",phone,specialization,ogrnip,profile_completed as \"profileCompleted\" FROM master_profiles WHERE user_id=%s", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"userId": user_id, "fullName": "", "profileCompleted": False}
    return dict(row)

@app.post("/master-profile")
def create_master_profile(p: MasterProfileModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO master_profiles (user_id,full_name,passport,inn,contract_type,bank_account,bank_name,phone,specialization,ogrnip,profile_completed)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
        ON CONFLICT (user_id) DO UPDATE SET
            full_name=EXCLUDED.full_name,passport=EXCLUDED.passport,inn=EXCLUDED.inn,
            contract_type=EXCLUDED.contract_type,bank_account=EXCLUDED.bank_account,
            bank_name=EXCLUDED.bank_name,phone=EXCLUDED.phone,
            specialization=EXCLUDED.specialization,ogrnip=EXCLUDED.ogrnip,profile_completed=TRUE
        RETURNING id,user_id as "userId",full_name as "fullName",passport,inn,
            contract_type as "contractType",bank_account as "bankAccount",
            bank_name as "bankName",phone,specialization,ogrnip,profile_completed as "profileCompleted"
    """, (p.userId,p.fullName,p.passport,p.inn,p.contractType,p.bankAccount,p.bankName,p.phone,p.specialization,p.ogrnip))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.get("/contracts")
def get_contracts():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,master_id as \"masterId\",master_name as \"masterName\",contract_type as \"contractType\",contract_number as \"contractNumber\",project,start_date as \"startDate\",end_date as \"endDate\" FROM contracts ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/contracts")
def create_contract(c: ContractModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO contracts (master_id,master_name,contract_type,contract_number,project,start_date,end_date) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (c.masterId,c.masterName,c.contractType,c.contractNumber,c.project,c.startDate,c.endDate))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.delete("/contracts/{id}")
def delete_contract(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM contracts WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/interim-acts")
def get_interim_acts():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,master_id as \"masterId\",master_name as \"masterName\",project,period_start as \"periodStart\",period_end as \"periodEnd\",total_amount as \"totalAmount\",paid_amount as \"paidAmount\",contract_id as \"contractId\",status FROM interim_acts ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/interim-acts")
def create_interim_act(a: InterimActModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO interim_acts (master_id,master_name,project,period_start,period_end,total_amount,paid_amount,contract_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (a.masterId,a.masterName,a.project,a.periodStart,a.periodEnd,a.totalAmount,a.paidAmount,a.contractId))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/interim-acts/{id}")
def update_interim_act(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    if 'status' in data:
        cur.execute("UPDATE interim_acts SET status=%s WHERE id=%s", (data['status'],id))
    if 'paidAmount' in data:
        cur.execute("UPDATE interim_acts SET paid_amount=%s WHERE id=%s", (data['paidAmount'],id))
    conn.close()
    return {"ok": True}

@app.delete("/interim-acts/{id}")
def delete_interim_act(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM interim_acts WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/timesheet/{staff_id}")
def get_timesheet(staff_id: int):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT day FROM timesheet WHERE staff_id=%s", (staff_id,))
    rows = cur.fetchall()
    conn.close()
    return {"days": [r['day'] for r in rows]}

@app.post("/timesheet")
def toggle_timesheet(data: TimesheetModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM timesheet WHERE staff_id=%s AND day=%s", (data.staffId,data.day))
    existing = cur.fetchone()
    if existing:
        cur.execute("DELETE FROM timesheet WHERE staff_id=%s AND day=%s", (data.staffId,data.day))
    else:
        cur.execute("INSERT INTO timesheet (staff_id,day) VALUES (%s,%s)", (data.staffId,data.day))
    conn.close()
    return {"ok": True}

@app.get("/rooms")
def get_rooms():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,project,name,floor_area as \"floorArea\",wall_area as \"wallArea\",ceiling_area as \"ceilingArea\",windows,doors,notes,floor,liter,room_type as \"roomType\" FROM rooms ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/rooms")
def create_room(r: RoomModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO rooms (project,name,floor_area,wall_area,ceiling_area,windows,doors,notes,floor,liter,room_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,project,name,floor_area as \"floorArea\",wall_area as \"wallArea\",ceiling_area as \"ceilingArea\",windows,doors,notes,floor,liter,room_type as \"roomType\"",
                (r.project,r.name,r.floorArea,r.wallArea,r.ceilingArea,r.windows,r.doors,r.notes,r.floor,r.liter,r.roomType))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/rooms/{id}")
def update_room(id: int, r: RoomModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE rooms SET floor=%s,liter=%s,room_type=%s, project=%s,name=%s,floor_area=%s,wall_area=%s,ceiling_area=%s,windows=%s,doors=%s,notes=%s WHERE id=%s",
                (r.project,r.name,r.floorArea,r.wallArea,r.ceilingArea,r.windows,r.doors,r.notes,id))
    conn.close()
    return {"ok": True}

@app.delete("/rooms/{id}")
def delete_room(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM rooms WHERE id=%s", (id,))
    cur.execute("DELETE FROM room_works WHERE room_id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/room-works")
def get_room_works():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,room_id as \"roomId\",project,room_name as \"roomName\",master_id as \"masterId\",master_name as \"masterName\",description,surface,unit,quantity,price_per_unit as \"pricePerUnit\",total,date,status,photo_url as \"photoUrl\",confirmed_by as \"confirmedBy\" FROM room_works ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/room-works")
def create_room_work(w: RoomWorkModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO room_works (room_id,project,room_name,master_id,master_name,description,surface,unit,quantity,price_per_unit,total,date,photo_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (w.roomId,w.project,w.roomName,w.masterId,w.masterName,w.description,w.surface,w.unit,w.quantity,w.pricePerUnit,w.total,w.date,w.photoUrl))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/room-works/{id}")
def update_room_work(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    if 'status' in data:
        cur.execute("UPDATE room_works SET status=%s,confirmed_by=%s WHERE id=%s",
                    (data['status'],data.get('confirmedBy',''),id))
    conn.close()
    return {"ok": True}

@app.get("/tools")
def get_tools():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,name,inventory_number as \"inventoryNumber\",cost,status,location,project,master_id as \"masterId\",master_name as \"masterName\",issue_type as \"issueType\",photo_url as \"photoUrl\",notes FROM tools ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/tools")
def create_tool(t: ToolModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO tools (name,inventory_number,cost,status,location,project,master_id,master_name,issue_type,photo_url,notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (t.name,t.inventoryNumber,t.cost,t.status,t.location,t.project,t.masterId,t.masterName,t.issueType,t.photoUrl,t.notes))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/tools/{id}")
def update_tool(id: int, t: ToolModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE tools SET name=%s,inventory_number=%s,cost=%s,status=%s,location=%s,project=%s,master_id=%s,master_name=%s,issue_type=%s,photo_url=%s,notes=%s WHERE id=%s",
                (t.name,t.inventoryNumber,t.cost,t.status,t.location,t.project,t.masterId,t.masterName,t.issueType,t.photoUrl,t.notes,id))
    conn.close()
    return {"ok": True}

@app.delete("/tools/{id}")
def delete_tool(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM tools WHERE id=%s", (id,))
    conn.close()
    return {"ok": True}

@app.get("/tool-history")
def get_tool_history():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,tool_id as \"toolId\",tool_name as \"toolName\",action,from_location as \"fromLocation\",to_location as \"toLocation\",master_name as \"masterName\",project,issue_type as \"issueType\",condition,date,created_by as \"createdBy\" FROM tool_history ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/tool-history")
def create_tool_history(h: ToolHistoryModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO tool_history (tool_id,tool_name,action,from_location,to_location,master_name,project,issue_type,condition,date,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (h.toolId,h.toolName,h.action,h.fromLocation,h.toLocation,h.masterName,h.project,h.issueType,h.condition,h.date,h.createdBy))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.get("/inventory")
def get_inventory():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM inventory ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/inventory")
def create_inventory(inv: InventoryModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO inventory (project,date,created_by,notes) VALUES (%s,%s,%s,%s) RETURNING *",
                (inv.project,inv.date,inv.createdBy,inv.notes))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/inventory/{id}")
def update_inventory(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    if 'status' in data:
        cur.execute("UPDATE inventory SET status=%s WHERE id=%s", (data['status'],id))
    conn.close()
    return {"ok": True}

@app.get("/inventory/{id}/items")
def get_inventory_items(id: int):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM inventory_items WHERE inventory_id=%s", (id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/inventory-items")
def create_inventory_item(item: InventoryItemModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO inventory_items (inventory_id,material_name,unit,expected,actual,difference,notes) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (item.inventoryId,item.materialName,item.unit,item.expected,item.actual,item.difference,item.notes))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.get("/pd-consents")
def get_pd_consents():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,user_id as \"userId\",signed_at as \"signedAt\",scan_url as \"scanUrl\",uploaded_by as \"uploadedBy\" FROM pd_consents")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/pd-consents")
def create_pd_consent(p: PdConsentModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        INSERT INTO pd_consents (user_id,signed_at,scan_url,uploaded_by)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (user_id) DO UPDATE SET
            signed_at=EXCLUDED.signed_at,scan_url=EXCLUDED.scan_url,uploaded_by=EXCLUDED.uploaded_by
        RETURNING id,user_id as "userId",signed_at as "signedAt",scan_url as "scanUrl",uploaded_by as "uploadedBy"
    """, (p.userId,p.signedAt,p.scanUrl,p.uploadedBy))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.delete("/pd-consents/{user_id}")
def delete_pd_consent(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM pd_consents WHERE user_id=%s", (user_id,))
    conn.close()
    return {"ok": True}

@app.post("/upload-photo")
async def upload_photo(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1]
    filename = str(uuid.uuid4()) + ext
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"url": "/uploads/" + filename}

@app.get("/room-windows")
def get_room_windows():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,room_id,name,width,height,window_type,reveal_depth,reveal_material,order_num FROM room_windows ORDER BY id")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"room_id":r[1],"name":r[2],"width":r[3],"height":r[4],"window_type":r[5],"reveal_depth":r[6],"reveal_material":r[7],"order_num":r[8]} for r in rows]

@app.post("/room-windows")
def create_room_window(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO room_windows (room_id,name,width,height,window_type,reveal_depth,reveal_material,order_num) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (data.get('roomId') or data.get('room_id'),data.get('name',''),float(data.get('width',0)),float(data.get('height',0)),data.get('windowType') or data.get('window_type','ПВХ'),float(data.get('revealDepth') or data.get('reveal_depth') or 0),data.get('revealMaterial') or data.get('reveal_material','Штукатурка'),int(data.get('orderNum') or data.get('order_num') or 0)))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

@app.get("/room-doors")
def get_room_doors():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,room_id,name,width,height,door_type,door_purpose,reveal_depth,reveal_material,order_num FROM room_doors ORDER BY id")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"room_id":r[1],"name":r[2],"width":r[3],"height":r[4],"door_type":r[5],"door_purpose":r[6],"reveal_depth":r[7],"reveal_material":r[8],"order_num":r[9]} for r in rows]

@app.post("/room-doors")
def create_room_door(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO room_doors (room_id,name,width,height,door_type,door_purpose,reveal_depth,reveal_material,order_num) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (data.get('roomId') or data.get('room_id'),data.get('name',''),float(data.get('width',0)),float(data.get('height',0)),data.get('doorType') or data.get('door_type','Деревянная'),data.get('doorPurpose') or data.get('door_purpose','Межкомнатная'),float(data.get('revealDepth') or data.get('reveal_depth') or 0),data.get('revealMaterial') or data.get('reveal_material','Штукатурка'),int(data.get('orderNum') or data.get('order_num') or 0)))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

@app.get("/messages")
def get_messages():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,chat_type,project_id,author_id,author_name,author_role,text,photo_url,created_at FROM messages ORDER BY created_at ASC LIMIT 200")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"chat_type":r[1],"project_id":r[2],"author_id":r[3],"author_name":r[4],"author_role":r[5],"text":r[6],"photo_url":r[7],"created_at":str(r[8])} for r in rows]

@app.post("/messages")
def create_message(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (chat_type,project_id,author_id,author_name,author_role,text,photo_url) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (data.get('chatType','company'),data.get('projectId'),data.get('authorId'),data.get('authorName',''),data.get('authorRole',''),data.get('text',''),data.get('photoUrl','')))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return row

import urllib.request
import json as json_lib

@app.post("/ai-chat")
def ai_chat(data: dict):
    from openai import OpenAI
    FOLDER_ID = YANDEX_FOLDER_ID
    API_KEY = YANDEX_API_KEY
    messages = data.get("messages", [])
    json_only = data.get("jsonOnly", False)
    skip_context = data.get("skipContext", False) or json_only

    if json_only:
        context = "Ты отвечаешь СТРОГО валидным JSON. Никакого markdown, никаких ```, никакого текста до или после JSON. Только сам JSON."
    elif skip_context:
        context = ""
    else:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name, status FROM projects")
        projects = cur.fetchall()
        cur.execute("SELECT name, quantity, unit FROM warehouse_main")
        materials = cur.fetchall()
        cur.execute("SELECT name, role FROM users WHERE role NOT IN ('заказчик','поставщик')")
        staff = cur.fetchall()
        cur.close()
        cur2 = conn.cursor()
        cur2.execute("SELECT name, quantity, unit, project FROM materials WHERE quantity > 0 ORDER BY project")
        obj_materials = cur2.fetchall()
        cur2.execute("SELECT project_name, brigade_name, status FROM brigade_contracts")
        brigades = cur2.fetchall()
        cur2.execute("SELECT project_name, amount, note FROM project_payments ORDER BY id DESC LIMIT 10")
        payments = cur2.fetchall()
        cur2.close()
        context = "Ты ИИ помощник строительной компании СтройКа. Отвечай кратко на русском.\n"
        context += "ПРОЕКТЫ ("+str(len(projects))+"): "+", ".join([p[0]+" ("+p[1]+")" for p in projects])+"\n"
        context += "СОТРУДНИКИ: "+", ".join([s[0]+" - "+s[1] for s in staff[:15]])+"\n"
        context += "СКЛАД ОСНОВНОЙ: "+", ".join([m[0]+": "+str(m[1])+" "+m[2] for m in materials[:20]])+"\n"
        context += "МАТЕРИАЛЫ НА ОБЪЕКТАХ: "+", ".join([m[0]+": "+str(m[1])+" "+m[2]+" ("+str(m[3])+")" for m in obj_materials[:20]])+"\n"
        context += "НАРЯДЫ: "+", ".join([b[0]+": "+b[1]+" - "+b[2] for b in brigades[:10]])+"\n"
        context += "ОПЛАТЫ: "+", ".join([pay[0]+": "+str(int(pay[1]))+" руб - "+str(pay[2]) for pay in payments[:10]])+"\n"
    import openai as oa
    client = oa.OpenAI(api_key=API_KEY, base_url="https://ai.api.cloud.yandex.net/v1", project=FOLDER_ID)
    user_text = messages[-1].get("content","") if messages else ""

    def _call(model_id, max_tokens):
        try:
            r = client.responses.create(
                model="gpt://"+FOLDER_ID+"/"+model_id,
                temperature=0.1 if json_only else 0.2,
                instructions=context,
                input=user_text,
                max_output_tokens=max_tokens,
            )
            return (r.output_text or ""), None
        except Exception as e:
            return "", str(e)

    primary_model = "qwen3.6-35b-a3b/latest" if json_only else "yandexgpt-5.1/latest"
    primary_tokens = 4000 if json_only else 2000
    answer, err = _call(primary_model, primary_tokens)
    if not (answer or "").strip():
        print("AI PRIMARY EMPTY model=" + primary_model + " err=" + str(err))
        fallback_model = "yandexgpt-5.1/latest" if json_only else "qwen3.6-35b-a3b/latest"
        print("AI FALLBACK trying " + fallback_model)
        answer, err = _call(fallback_model, primary_tokens)
        if not (answer or "").strip():
            print("AI FALLBACK ALSO EMPTY err=" + str(err))
            answer = "Ошибка: ИИ вернул пустой ответ. Попробуйте ещё раз или сократите запрос."
    print("AI ANSWER LEN:", len(answer or ""))
    print("AI ANSWER HEAD:", (answer or "")[:200])
    return {"response": answer}


@app.get("/warehouses")
def get_warehouses():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,name,city,address,notes FROM warehouses ORDER BY id")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"name":r[1],"city":r[2],"address":r[3],"notes":r[4]} for r in rows]

@app.post("/warehouses")
def create_warehouse(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO warehouses (name,city,address,notes) VALUES (%s,%s,%s,%s) RETURNING id,name,city,address,notes",
        (data.get("name",""),data.get("city",""),data.get("address",""),data.get("notes","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"name":row[1],"city":row[2],"address":row[3],"notes":row[4]}

@app.put("/warehouses/{id}")
def update_warehouse(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE warehouses SET name=%s,city=%s,address=%s,notes=%s WHERE id=%s RETURNING id,name,city,address,notes",
        (data.get("name",""),data.get("city",""),data.get("address",""),data.get("notes",""),id))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"name":row[1],"city":row[2],"address":row[3],"notes":row[4]}

@app.delete("/warehouses/{id}")
def delete_warehouse(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM warehouses WHERE id=%s",(id,))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.get("/company-requisites")
def get_company_requisites():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,full_name,short_name,inn,kpp,ogrn,legal_address,actual_address,phone,email,director_name,director_position,basis,bank_name,bik,rs,ks FROM company_requisites ORDER BY id LIMIT 1")
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row: return {}
    return {"id":row[0],"fullName":row[1],"shortName":row[2],"inn":row[3],"kpp":row[4],"ogrn":row[5],"legalAddress":row[6],"actualAddress":row[7],"phone":row[8],"email":row[9],"directorName":row[10],"directorPosition":row[11],"basis":row[12],"bankName":row[13],"bik":row[14],"rs":row[15],"ks":row[16]}

@app.post("/company-requisites")
def save_company_requisites(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM company_requisites")
    cur.execute("INSERT INTO company_requisites (full_name,short_name,inn,kpp,ogrn,legal_address,actual_address,phone,email,director_name,director_position,basis,bank_name,bik,rs,ks) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("fullName",""),data.get("shortName",""),data.get("inn",""),data.get("kpp",""),data.get("ogrn",""),data.get("legalAddress",""),data.get("actualAddress",""),data.get("phone",""),data.get("email",""),data.get("directorName",""),data.get("directorPosition",""),data.get("basis",""),data.get("bankName",""),data.get("bik",""),data.get("rs",""),data.get("ks","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.get("/company-documents")
def get_company_documents():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,company_id,name,doc_type,file_url,expires_at,uploaded_by FROM company_documents ORDER BY id")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"companyId":r[1],"name":r[2],"docType":r[3],"fileUrl":r[4],"expiresAt":r[5],"uploadedBy":r[6]} for r in rows]

@app.post("/company-documents")
def create_company_document(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO company_documents (company_id,name,doc_type,file_url,expires_at,uploaded_by) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("companyId"),data.get("name",""),data.get("docType",""),data.get("fileUrl",""),data.get("expiresAt",""),data.get("uploadedBy","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.delete("/company-documents/{id}")
def delete_company_document(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM company_documents WHERE id=%s",(id,))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.get("/project-stages")
def get_project_stages():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,project_id,project_name,name,status,start_date,end_date,progress,responsible,notes,order_num FROM project_stages ORDER BY order_num,id")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"projectId":r[1],"projectName":r[2],"name":r[3],"status":r[4],"startDate":r[5],"endDate":r[6],"progress":r[7],"responsible":r[8],"notes":r[9],"orderNum":r[10]} for r in rows]

@app.post("/project-stages")
def create_project_stage(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO project_stages (project_id,project_name,name,status,start_date,end_date,progress,responsible,notes,order_num) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("projectId"),data.get("projectName",""),data.get("name",""),data.get("status","Не начат"),data.get("startDate",""),data.get("endDate",""),int(data.get("progress",0)),data.get("responsible",""),data.get("notes",""),int(data.get("orderNum",0))))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.put("/project-stages/{id}")
def update_project_stage(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE project_stages SET name=%s,status=%s,start_date=%s,end_date=%s,progress=%s,responsible=%s,notes=%s WHERE id=%s",
        (data.get("name",""),data.get("status",""),data.get("startDate",""),data.get("endDate",""),int(data.get("progress",0)),data.get("responsible",""),data.get("notes",""),id))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.delete("/project-stages/{id}")
def delete_project_stage(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM project_stages WHERE id=%s",(id,))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.get("/project-checklists")
def get_project_checklists():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,project_id,project_name,name,template,status,created_by,created_at FROM project_checklists ORDER BY id")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"projectId":r[1],"projectName":r[2],"name":r[3],"template":r[4],"status":r[5],"createdBy":r[6],"createdAt":str(r[7])} for r in rows]

@app.post("/project-checklists")
def create_project_checklist(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO project_checklists (project_id,project_name,name,template,status,created_by,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("projectId"),data.get("projectName",""),data.get("name",""),data.get("template",""),data.get("status","В работе"),data.get("createdBy",""),data.get("createdAt","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.get("/checklist-items/{checklist_id}")
def get_checklist_items(checklist_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,checklist_id,name,checked,checked_by,checked_at,order_num FROM checklist_items WHERE checklist_id=%s ORDER BY order_num,id",(checklist_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"checklistId":r[1],"name":r[2],"checked":r[3],"checkedBy":r[4],"checkedAt":r[5],"orderNum":r[6]} for r in rows]

@app.post("/checklist-items")
def create_checklist_item(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO checklist_items (checklist_id,name,checked,checked_by,checked_at,order_num) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("checklistId"),data.get("name",""),data.get("checked",False),data.get("checkedBy",""),data.get("checkedAt",""),int(data.get("orderNum",0))))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.put("/checklist-items/{id}")
def update_checklist_item(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE checklist_items SET checked=%s,checked_by=%s,checked_at=%s WHERE id=%s",
        (data.get("checked",False),data.get("checkedBy",""),data.get("checkedAt",""),id))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.get("/prescriptions")
def get_prescriptions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,project_name,number,issued_by,issued_by_role,violation,deadline,responsible,status,photo_url,fix_photo_url,fix_notes FROM prescriptions ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"projectName":r[1],"number":r[2],"issuedBy":r[3],"issuedByRole":r[4],"violation":r[5],"deadline":r[6],"responsible":r[7],"status":r[8],"photoUrl":r[9],"fixPhotoUrl":r[10],"fixNotes":r[11]} for r in rows]

@app.post("/prescriptions")
def create_prescription(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO prescriptions (project_name,number,issued_by,issued_by_role,violation,deadline,responsible,status,photo_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("projectName",""),data.get("number",""),data.get("issuedBy",""),data.get("issuedByRole",""),data.get("violation",""),data.get("deadline",""),data.get("responsible",""),data.get("status","Открыто"),data.get("photoUrl","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.put("/prescriptions/{id}")
def update_prescription(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE prescriptions SET status=%s,fix_photo_url=%s,fix_notes=%s WHERE id=%s",
        (data.get("status",""),data.get("fixPhotoUrl",""),data.get("fixNotes",""),id))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.get("/project-chat/{project_name}")
def get_project_chat(project_name: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,project_name,author_id,author_name,author_role,text,photo_url,created_at FROM project_chat WHERE project_name=%s ORDER BY created_at ASC LIMIT 200",(project_name,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"projectName":r[1],"authorId":r[2],"authorName":r[3],"authorRole":r[4],"text":r[5],"photoUrl":r[6],"createdAt":str(r[7])} for r in rows]

@app.post("/project-chat")
def create_project_chat(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO project_chat (project_name,author_id,author_name,author_role,text,photo_url) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("projectName",""),data.get("authorId"),data.get("authorName",""),data.get("authorRole",""),data.get("text",""),data.get("photoUrl","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.get("/unexpected-works")
def get_unexpected_works():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,project_name,description,unit,quantity,price,total,added_by,added_by_role,status,approved_by,approved_at,notes,photo_url FROM unexpected_works ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"projectName":r[1],"description":r[2],"unit":r[3],"quantity":r[4],"price":r[5],"total":r[6],"addedBy":r[7],"addedByRole":r[8],"status":r[9],"approvedBy":r[10],"approvedAt":r[11],"notes":r[12],"photoUrl":r[13]} for r in rows]

@app.post("/unexpected-works")
def create_unexpected_work(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO unexpected_works (project_name,description,unit,quantity,price,total,added_by,added_by_role,status,notes,photo_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("projectName",""),data.get("description",""),data.get("unit","шт"),float(data.get("quantity",0)),float(data.get("price",0)),float(data.get("total",0)),data.get("addedBy",""),data.get("addedByRole",""),data.get("status","Ожидает согласования"),data.get("notes",""),data.get("photoUrl","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.put("/unexpected-works/{id}")
def update_unexpected_work(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE unexpected_works SET status=%s,price=%s,total=%s,approved_by=%s,approved_at=%s WHERE id=%s",
        (data.get("status",""),float(data.get("price",0)),float(data.get("total",0)),data.get("approvedBy",""),data.get("approvedAt",""),id))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.post("/parse-smeta")
async def parse_smeta(file: UploadFile = File(...)):
    import tempfile, os
    try:
        import openpyxl
    except ImportError:
        return {"error": "openpyxl not installed"}
    
    contents = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    
    try:
        wb = openpyxl.load_workbook(tmp_path, data_only=True)
        ws = wb.active
        results = []
        current_section = "Без раздела"
        data_start_row = 1
        file_type = "unknown"
        
        for i, row in enumerate(ws.iter_rows(max_row=60, values_only=True)):
            vals = [str(v).strip() for v in row if v is not None]
            row_text = " ".join(vals).lower()
            if "обоснование" in row_text and "наименование" in row_text and ("работ" in row_text or "затрат" in row_text):
                data_start_row = i + 2
                file_type = "lsr"
                break
            elif "наименование" in row_text and "ед" in row_text and "кол" in row_text and "обоснование" not in row_text:
                data_start_row = i + 2
                file_type = "defect"
                break
            elif "обоснование" in row_text and "наименование" in row_text and "общее" in row_text:
                data_start_row = i + 2
                file_type = "vedomost"
                break
        
        work_prefixes = ["ГЭСН", "ФЕР", "ТЕР", "ГЭСНм", "ФЕРм", "ТЕРм", "ГЭСНи", "ФЕРи", "ГЭСНр", "ФЕРр", "ТЕРр"]
        material_prefixes = ["ФСБЦ", "ФССЦ", "ТЦ_", "КАЦ", "МАТ"]
        
        for i, row in enumerate(ws.iter_rows(min_row=data_start_row, values_only=True)):
            try:
                first_val = str(row[0]).strip() if row[0] is not None else ""
                name_col = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                obosn = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                
                if "Раздел" in first_val or "РАЗДЕЛ" in first_val:
                    current_section = first_val
                    continue
                
                if file_type == "lsr":
                    if "Всего по позиции" in name_col:
                        if results and results[-1].get("total", 0) == 0:
                            try:
                                v = round(float(row[13]), 2) if len(row) > 13 and row[13] and isinstance(row[13], (int,float)) else 0
                                if v > 0:
                                    results[-1]["total"] = v
                                    if results[-1].get("type") == "work":
                                        results[-1]["totalWork"] = v
                                    else:
                                        results[-1]["totalMaterial"] = v
                            except:
                                pass
                        continue
                    
                    num = row[0]
                    if not num:
                        continue
                    try:
                        float(str(num).strip())
                    except:
                        continue
                    
                    if not name_col or len(name_col) < 5:
                        continue
                    if any(x in name_col for x in ["Объем=", "Итого", "ФОТ", "Всего", "Вспомогательные ненормируемые"]):
                        continue
                    if "Пр/" in obosn or "648/" in obosn:
                        continue
                    
                    if any(obosn.startswith(x) for x in work_prefixes):
                        item_type = "work"
                    elif any(obosn.startswith(x) for x in material_prefixes):
                        item_type = "material"
                    else:
                        item_type = "work"
                    
                    unit = str(row[7]).strip() if len(row) > 7 and row[7] else "шт"
                    qty = float(row[8]) if len(row) > 8 and isinstance(row[8], (int,float)) else 0

                    work_total = 0
                    mat_total = 0
                    try:
                        if item_type == "work" and len(row) > 13 and row[13] and isinstance(row[13], (int,float)):
                            work_total = round(float(row[13]), 2)
                    except:
                        pass
                    try:
                        if item_type == "material" and len(row) > 15 and row[15] and isinstance(row[15], (int,float)):
                            mat_total = round(float(row[15]), 2)
                    except:
                        pass

                    results.append({
                        "section": current_section,
                        "name": name_col,
                        "unit": unit,
                        "quantity": round(qty, 4),
                        "total": mat_total if item_type == "material" else work_total,
                        "totalWork": work_total,
                        "totalMaterial": mat_total,
                        "type": item_type
                    })
                
                elif file_type == "defect":
                    if all(v is None or (isinstance(v, (int,float)) and v < 10) for v in row[:5]):
                        continue
                    name = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                    unit = str(row[2]).strip() if len(row) > 2 and row[2] else "шт"
                    try:
                        qty = float(row[3]) if len(row) > 3 and row[3] and isinstance(row[3], (int,float)) else 0
                    except:
                        qty = 0
                    if name and len(name) > 5 and name not in ["Наименование", "2"] and not all(c.isdigit() or c == " " for c in name):
                        results.append({"section": current_section, "name": name, "unit": unit, "quantity": qty, "total": 0, "type": "work"})
                
                elif file_type == "vedomost":
                    name = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                    unit = str(row[3]).strip() if len(row) > 3 and row[3] else "шт"
                    try:
                        qty = float(row[4]) if len(row) > 4 and row[4] and isinstance(row[4], (int,float)) else 0
                        total = float(row[6]) if len(row) > 6 and row[6] and isinstance(row[6], (int,float)) else 0
                    except:
                        qty = total = 0
                    if name and len(name) > 5 and name not in ["Наименование", "3"]:
                        results.append({"section": current_section, "name": name, "unit": unit, "quantity": round(qty,4), "total": round(total,2), "type": "material"})
            except:
                continue
        
        os.unlink(tmp_path)
        return {"items": results, "count": len(results)}
    except Exception as e:
        try:
            os.unlink(tmp_path)
        except:
            pass
        return {"error": str(e)}


@app.get("/estimates")
def get_estimates():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,project_id,project_name,name,version,sections_json,status,COALESCE(is_template,FALSE) FROM estimates ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    import json as j
    result = []
    for r in rows:
        try:
            sections = j.loads(r[5]) if r[5] else []
        except:
            sections = []
        result.append({"id":r[0],"projectId":r[1],"projectName":r[2],"name":r[3],"version":r[4],"sections":sections,"smetaType":r[6] or "Заказчик","isTemplate":bool(r[7])})
    return result

@app.post("/estimates")
def create_estimate(data: dict):
    import json as j
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO estimates (project_id,project_name,name,version,sections_json) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (data.get("projectId"),data.get("projectName",""),data.get("name",""),data.get("version","1.0"),j.dumps(data.get("sections",[]),ensure_ascii=False)))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.put("/estimates/{id}")
def update_estimate(id: int, data: dict):
    import json as j
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT sections_json, version FROM estimates WHERE id=%s", (id,))
    prev = cur.fetchone()
    if prev and prev[0]:
        try:
            old_sections = j.loads(prev[0]) if prev[0] else []
            total = 0
            for s in old_sections:
                for it in (s.get("items") or []):
                    if it.get("isImported"):
                        total += float(it.get("priceWork") or 0)
                    else:
                        total += float(it.get("quantity") or 0) * (float(it.get("priceWork") or 0) + float(it.get("priceMaterial") or 0))
            cur.execute("INSERT INTO estimate_versions (estimate_id, version_label, sections_json, total, comment, created_by) VALUES (%s,%s,%s,%s,%s,%s)",
                (id, prev[1] or "", prev[0], total, data.get("versionComment",""), data.get("updatedBy","")))
        except Exception:
            pass
    cur.execute("UPDATE estimates SET name=%s,version=%s,sections_json=%s WHERE id=%s",
        (data.get("name",""),data.get("version","1.0"),j.dumps(data.get("sections",[]),ensure_ascii=False),id))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.put("/estimates/{id}/toggle-template")
def toggle_estimate_template(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE estimates SET is_template = NOT COALESCE(is_template,FALSE) WHERE id=%s RETURNING is_template", (id,))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"ok": True, "isTemplate": bool(row[0]) if row else False}

@app.get("/estimates/{id}/versions")
def get_estimate_versions(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, version_label, total, comment, created_by, created_at FROM estimate_versions WHERE estimate_id=%s ORDER BY id DESC", (id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"versionLabel":r[1] or "","total":float(r[2] or 0),"comment":r[3] or "","createdBy":r[4] or "","createdAt":str(r[5])} for r in rows]

@app.get("/estimate-version/{version_id}")
def get_estimate_version_detail(version_id: int):
    import json as j
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, estimate_id, version_label, sections_json, total, comment, created_by, created_at FROM estimate_versions WHERE id=%s", (version_id,))
    r = cur.fetchone()
    cur.close(); conn.close()
    if not r:
        raise HTTPException(status_code=404, detail="version not found")
    try:
        sections = j.loads(r[3]) if r[3] else []
    except:
        sections = []
    return {"id":r[0],"estimateId":r[1],"versionLabel":r[2] or "","sections":sections,"total":float(r[4] or 0),"comment":r[5] or "","createdBy":r[6] or "","createdAt":str(r[7])}

@app.delete("/estimates/{id}")
def delete_estimate(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM estimates WHERE id=%s",(id,))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.get("/brigade-contracts")
def get_brigade_contracts(project_name: str = None):
    conn = get_db()
    cur = conn.cursor()
    if project_name:
        cur.execute("SELECT id,project_id,project_name,brigade_name,contractor_type,contractor_id,total_amount,status,signed_at,notes,created_at,pricelist_id FROM brigade_contracts WHERE project_name=%s ORDER BY id DESC", (project_name,))
    else:
        cur.execute("SELECT id,project_id,project_name,brigade_name,contractor_type,contractor_id,total_amount,status,signed_at,notes,created_at,pricelist_id FROM brigade_contracts ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"projectId":r[1],"projectName":r[2],"brigadeName":r[3],"contractorType":r[4],"contractorId":r[5],"totalAmount":float(r[6] or 0),"status":r[7],"signedAt":str(r[8]) if r[8] else "","notes":r[9] or "","createdAt":str(r[10]),"pricelistId":r[11]} for r in rows]

@app.post("/brigade-contracts")
def create_brigade_contract(data: dict):
    conn = get_db()
    cur = conn.cursor()
    pricelist_id = data.get("pricelistId") or None
    cur.execute("INSERT INTO brigade_contracts (project_id,project_name,brigade_name,contractor_type,contractor_id,total_amount,status,notes,pricelist_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("projectId") or None,data.get("projectName",""),data.get("brigadeName",""),data.get("contractorType","Бригада"),data.get("contractorId") or None,data.get("totalAmount",0),data.get("status","Черновик"),data.get("notes",""),pricelist_id))
    conn.commit()
    row = cur.fetchone()
    new_id = row[0]
    inserted = 0
    if pricelist_id:
        try:
            pl_id_int = int(pricelist_id)
            cur.execute("SELECT coefficient FROM pricelists WHERE id=%s", (pl_id_int,))
            cr = cur.fetchone()
            coef = float(cr[0] or 1.0) if cr else 1.0
            cur.execute("SELECT name, unit, price, category FROM pricelist_items WHERE pricelist_id=%s AND (item_type IS NULL OR item_type='work')", (pl_id_int,))
            for it in cur.fetchall():
                price = float(it[2] or 0)
                cur.execute("INSERT INTO brigade_contract_items (contract_id, estimate_section, description, unit, quantity, price_smeta, price_brigade, done_quantity) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (new_id, it[3] or "", it[0], it[1] or "шт", 0, price, round(price * coef, 2), 0))
                inserted += 1
            conn.commit()
        except Exception as e:
            print("AUTO-LOAD FROM PRICELIST ERROR:", str(e))
    cur.close(); conn.close()
    return {"id": new_id, "ok": True, "itemsLoaded": inserted}

@app.post("/brigade-contracts/{contract_id}/load-from-pricelist")
def load_brigade_items_from_pricelist(contract_id: int, with_materials: bool = False):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT pricelist_id FROM brigade_contracts WHERE id=%s", (contract_id,))
    r = cur.fetchone()
    if not r or not r[0]:
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="К наряду не привязан прайс-лист")
    pl_id = int(r[0])
    cur.execute("SELECT coefficient FROM pricelists WHERE id=%s", (pl_id,))
    cr = cur.fetchone()
    coef = float(cr[0] or 1.0) if cr else 1.0
    cur.execute("SELECT description FROM brigade_contract_items WHERE contract_id=%s", (contract_id,))
    existing_names = {row[0] for row in cur.fetchall()}
    if with_materials:
        cur.execute("SELECT name, unit, price, category, item_type FROM pricelist_items WHERE pricelist_id=%s", (pl_id,))
    else:
        cur.execute("SELECT name, unit, price, category, item_type FROM pricelist_items WHERE pricelist_id=%s AND (item_type IS NULL OR item_type='work')", (pl_id,))
    inserted = 0
    for it in cur.fetchall():
        if it[0] in existing_names:
            continue
        price = float(it[2] or 0)
        cur.execute("INSERT INTO brigade_contract_items (contract_id, estimate_section, description, unit, quantity, price_smeta, price_brigade, done_quantity) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (contract_id, it[3] or "", it[0], it[1] or "шт", 0, price, round(price * coef, 2), 0))
        inserted += 1
    conn.commit(); cur.close(); conn.close()
    return {"ok": True, "itemsLoaded": inserted}

@app.put("/brigade-contracts/{id}")
def update_brigade_contract(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE brigade_contracts SET brigade_name=%s,contractor_type=%s,total_amount=%s,status=%s,signed_at=%s,notes=%s,pricelist_id=%s WHERE id=%s",
        (data.get("brigadeName",""),data.get("contractorType","Бригада"),data.get("totalAmount",0),data.get("status","Черновик"),data.get("signedAt") or None,data.get("notes",""),data.get("pricelistId") or None,id))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.delete("/brigade-contracts/{id}")
def delete_brigade_contract(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM brigade_contracts WHERE id=%s",(id,))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.post("/estimates/{estimate_id}/distribute")
def distribute_estimate_to_brigades(estimate_id: int, data: dict):
    import json as _json
    assignments = data.get("assignments") or []
    default_coef = float(data.get("defaultCoefficient") or 0.6)
    if not assignments:
        raise HTTPException(status_code=400, detail="Нет распределений")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, project_id, project_name FROM estimates WHERE id=%s", (estimate_id,))
    est = cur.fetchone()
    if not est:
        cur.close(); conn.close()
        raise HTTPException(status_code=404, detail="Смета не найдена")
    estimate_name, project_id, project_name = est[0] or "", est[1], est[2] or ""

    # group assignments by brigade
    brigades_map = {}
    for a in assignments:
        bname = (a.get("brigadeName") or "").strip()
        if not bname:
            continue
        key = bname.lower()
        if key not in brigades_map:
            brigades_map[key] = {
                "brigadeName": bname,
                "contractorType": a.get("contractorType") or "Своя бригада",
                "contractorId": a.get("contractorId"),
                "pricelistId": a.get("pricelistId"),
                "items": [],
            }
        brigades_map[key]["items"].append(a)

    # Load pricelists once for coefficient lookup
    cur.execute("SELECT id, coefficient FROM pricelists")
    pl_coef = {r[0]: float(r[1] or 1.0) for r in cur.fetchall()}

    created = []
    for bdata in brigades_map.values():
        # find coefficient
        pl_id = bdata.get("pricelistId")
        try:
            pl_id = int(pl_id) if pl_id else None
        except Exception:
            pl_id = None
        coef = pl_coef.get(pl_id, default_coef) if pl_id else default_coef
        # create brigade_contract
        cur.execute("""INSERT INTO brigade_contracts (project_id, project_name, brigade_name, contractor_type, contractor_id, total_amount, status, notes, pricelist_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (project_id or None, project_name, bdata["brigadeName"], bdata["contractorType"], bdata.get("contractorId") or None, 0, "Черновик", "Создан из сметы: " + estimate_name, pl_id))
        contract_id = cur.fetchone()[0]
        total = 0
        for it in bdata["items"]:
            qty = float(it.get("quantity") or 0)
            price_smeta = float(it.get("priceSmeta") or it.get("priceWork") or 0)
            price_brigade = round(price_smeta * coef, 2)
            cur.execute("""INSERT INTO brigade_contract_items (contract_id, estimate_section, description, unit, quantity, price_smeta, price_brigade, done_quantity)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (contract_id, it.get("section",""), it.get("name",""), it.get("unit","шт"), qty, price_smeta, price_brigade, 0))
            total += qty * price_brigade
        cur.execute("UPDATE brigade_contracts SET total_amount=%s WHERE id=%s", (round(total, 2), contract_id))
        created.append({"id": contract_id, "brigadeName": bdata["brigadeName"], "totalAmount": round(total, 2), "itemsCount": len(bdata["items"])})

    conn.commit()
    cur.close(); conn.close()
    return {"ok": True, "createdContracts": created}

@app.post("/estimates/{estimate_id}/ai-distribute-suggest")
def ai_suggest_distribution(estimate_id: int, data: dict):
    import openai as oa
    import json as _json
    brigade_names = data.get("brigadeNames") or []
    if not brigade_names:
        raise HTTPException(status_code=400, detail="Передайте список бригад (brigadeNames)")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, sections_json FROM estimates WHERE id=%s", (estimate_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        raise HTTPException(status_code=404, detail="Смета не найдена")
    try:
        sections = _json.loads(row[1]) if row[1] else []
    except Exception:
        sections = []
    cur.close(); conn.close()

    # Flatten items
    items = []
    for s in sections:
        for it in (s.get("items") or []):
            items.append({"section": s.get("name",""), "name": it.get("name",""), "unit": it.get("unit",""), "quantity": it.get("quantity",0)})

    if not items:
        return {"ok": True, "assignments": []}

    instructions = "Ты отвечаешь СТРОГО валидным JSON. Никакого markdown, ```, только сам JSON."
    prompt = ("Распредели позиции сметы между бригадами по специализации.\n\nБРИГАДЫ:\n" +
              "\n".join("- " + b for b in brigade_names) +
              "\n\nПОЗИЦИИ:\n" +
              "\n".join(str(i+1) + ". [" + it["section"] + "] " + it["name"] for i, it in enumerate(items)) +
              "\n\nОТВЕТЬ JSON формате:\n{\"assignments\": [{\"index\": номер_позиции_с_1, \"brigadeName\": \"имя бригады из списка выше\"}]}\n" +
              "Привязывай позицию к бригаде по специализации. Если непонятно — выбирай 'Общестроительные' или первую общестроительную бригаду из списка.")

    client = oa.OpenAI(api_key=YANDEX_API_KEY, base_url="https://ai.api.cloud.yandex.net/v1", project=YANDEX_FOLDER_ID)
    raw = ""
    for model_id in ("qwen3.6-35b-a3b/latest", "yandexgpt-5.1/latest"):
        try:
            r = client.responses.create(
                model="gpt://" + YANDEX_FOLDER_ID + "/" + model_id,
                temperature=0.1,
                instructions=instructions,
                input=prompt,
                max_output_tokens=4000,
            )
            raw = (r.output_text or "").strip()
            if raw:
                break
        except Exception as e:
            print("AI-DISTRIBUTE ERROR:", str(e))

    if not raw:
        raise HTTPException(status_code=500, detail="ИИ не ответил")

    import re as _re
    clean = _re.sub(r"^```(?:json)?\s*", "", raw).strip()
    clean = _re.sub(r"\s*```\s*$", "", clean).strip()
    s_idx = clean.find("{"); e_idx = clean.rfind("}")
    parsed = None
    if s_idx >= 0 and e_idx > s_idx:
        try:
            parsed = _json.loads(clean[s_idx:e_idx+1])
        except Exception:
            parsed = None
    if not parsed or not isinstance(parsed.get("assignments"), list):
        raise HTTPException(status_code=500, detail="ИИ вернул не JSON")

    # Map index -> brigade
    result = []
    for a in parsed["assignments"]:
        idx = int(a.get("index", 0)) - 1
        if 0 <= idx < len(items):
            result.append({"itemIndex": idx, "brigadeName": str(a.get("brigadeName") or "")})
    return {"ok": True, "assignments": result, "items": items}

@app.get("/brigade-contract-items/{contract_id}")
def get_brigade_contract_items(contract_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,contract_id,estimate_section,description,unit,quantity,price_smeta,price_brigade,done_quantity FROM brigade_contract_items WHERE contract_id=%s ORDER BY id", (contract_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    def _status(q, done):
        try:
            q = float(q or 0); done = float(done or 0)
        except Exception:
            return "Не начато"
        if q > 0 and done >= q:
            return "Выполнено"
        if done > 0:
            return "В работе"
        return "Не начато"
    return [{"id":r[0],"contractId":r[1],"estimateSection":r[2],"name":r[3],"unit":r[4],"quantity":float(r[5] or 0),"priceSmeta":float(r[6] or 0),"priceBrigade":float(r[7] or 0),"doneQuantity":float(r[8] or 0),"status":_status(r[5], r[8])} for r in rows]

@app.post("/brigade-contract-items")
def create_brigade_contract_item(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO brigade_contract_items (contract_id,estimate_section,description,unit,quantity,price_smeta,price_brigade,done_quantity) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("contractId"),data.get("estimateSection",""),data.get("name","") or data.get("description",""),data.get("unit",""),data.get("quantity",0),data.get("priceSmeta",0),data.get("priceBrigade",0),data.get("doneQuantity",0)))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.put("/brigade-contract-items/{id}")
def update_brigade_contract_item(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE brigade_contract_items SET quantity=%s,price_brigade=%s,price_smeta=%s,done_quantity=%s WHERE id=%s",
        (data.get("quantity",0),data.get("priceBrigade",0),data.get("priceSmeta",0),data.get("doneQuantity",0),id))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.delete("/brigade-contract-items/{id}")
def delete_brigade_contract_item(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM brigade_contract_items WHERE id=%s",(id,))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.get("/brigade-acts")
def get_brigade_acts(contract_id: int = None):
    conn = get_db()
    cur = conn.cursor()
    if contract_id:
        cur.execute("SELECT id,contract_id,project_name,brigade_name,period_from,period_to,total_amount,status,created_at FROM brigade_acts WHERE contract_id=%s ORDER BY id DESC", (contract_id,))
    else:
        cur.execute("SELECT id,contract_id,project_name,brigade_name,period_from,period_to,total_amount,status,created_at FROM brigade_acts ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"contractId":r[1],"projectName":r[2],"brigadeName":r[3],"periodFrom":str(r[4]) if r[4] else "","periodTo":str(r[5]) if r[5] else "","totalAmount":float(r[6] or 0),"status":r[7],"createdAt":str(r[8])} for r in rows]

@app.post("/brigade-acts")
def create_brigade_act(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO brigade_acts (contract_id,project_name,brigade_name,period_from,period_to,total_amount,status) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("contractId"),data.get("projectName",""),data.get("brigadeName",""),data.get("periodFrom") or None,data.get("periodTo") or None,data.get("totalAmount",0),data.get("status","Черновик")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.get("/material-transfers")
def get_material_transfers(project_name: str = None):
    conn = get_db()
    cur = conn.cursor()
    if project_name:
        cur.execute("SELECT id,project_name,from_location,to_person,to_person_role,material_name,quantity,unit,transfer_date,signed,signed_at,notes,created_by,created_at FROM material_transfers WHERE project_name=%s ORDER BY id DESC", (project_name,))
    else:
        cur.execute("SELECT id,project_name,from_location,to_person,to_person_role,material_name,quantity,unit,transfer_date,signed,signed_at,notes,created_by,created_at FROM material_transfers ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"projectName":r[1],"fromLocation":r[2],"toPerson":r[3],"toPersonRole":r[4],"materialName":r[5],"quantity":float(r[6] or 0),"unit":r[7],"transferDate":str(r[8]) if r[8] else "","signed":r[9],"signedAt":str(r[10]) if r[10] else "","notes":r[11] or "","createdBy":r[12] or "","createdAt":str(r[13])} for r in rows]

@app.post("/material-transfers")
def create_material_transfer(data: dict):
    from_location = data.get("fromLocation", "Основной склад")
    material_name = data.get("materialName", "")
    qty = float(data.get("quantity", 0) or 0)
    if not material_name or qty <= 0:
        raise HTTPException(status_code=400, detail="Укажите материал и количество больше 0")

    conn = get_db()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        if from_location == "Основной склад":
            cur.execute("SELECT id, quantity FROM warehouse_main WHERE name=%s FOR UPDATE", (material_name,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=400, detail="Материал «"+material_name+"» не найден на основном складе")
            stock_id, stock_qty = row[0], float(row[1] or 0)
            if stock_qty < qty:
                raise HTTPException(status_code=400, detail="На основном складе только "+str(stock_qty)+", запрошено "+str(qty))
            cur.execute("UPDATE warehouse_main SET quantity=quantity-%s WHERE id=%s", (qty, stock_id))
        else:
            cur.execute("SELECT id, quantity FROM materials WHERE name=%s AND project=%s FOR UPDATE", (material_name, from_location))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=400, detail="Материал «"+material_name+"» не найден на складе объекта «"+from_location+"»")
            stock_id, stock_qty = row[0], float(row[1] or 0)
            if stock_qty < qty:
                raise HTTPException(status_code=400, detail="На складе «"+from_location+"» только "+str(stock_qty)+", запрошено "+str(qty))
            cur.execute("UPDATE materials SET quantity=quantity-%s WHERE id=%s", (qty, stock_id))

        cur.execute("INSERT INTO material_transfers (project_name,from_location,to_person,to_person_role,material_name,quantity,unit,transfer_date,notes,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (data.get("projectName",""), from_location, data.get("toPerson",""), data.get("toPersonRole",""), material_name, qty, data.get("unit","шт"), data.get("transferDate") or None, data.get("notes",""), data.get("createdBy","")))
        new_id = cur.fetchone()[0]

        cur.execute("INSERT INTO warehouse_history (material,type,quantity,date,project,issued_by,date_time) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (material_name, "расход", qty, data.get("transferDate") or None, from_location, data.get("createdBy",""), __import__("datetime").datetime.now().strftime("%d.%m.%Y, %H:%M")))

        conn.commit()
        return {"id": new_id, "ok": True}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.put("/material-transfers/{id}/sign")
def sign_material_transfer(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE material_transfers SET signed=TRUE,signed_at=NOW() WHERE id=%s",(id,))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.delete("/material-transfers/{id}")
def delete_material_transfer(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM material_transfers WHERE id=%s",(id,))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.get("/supplier-catalog")
def get_supplier_catalog(supplier_id: int = None):
    conn = get_db()
    cur = conn.cursor()
    if supplier_id:
        cur.execute("SELECT id,supplier_id,supplier_name,material_name,unit,price,min_quantity,delivery_days,in_stock,notes FROM supplier_catalog WHERE supplier_id=%s ORDER BY material_name", (supplier_id,))
    else:
        cur.execute("SELECT id,supplier_id,supplier_name,material_name,unit,price,min_quantity,delivery_days,in_stock,notes FROM supplier_catalog ORDER BY material_name")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"supplierId":r[1],"supplierName":r[2],"materialName":r[3],"unit":r[4],"price":float(r[5] or 0),"minQuantity":float(r[6] or 1),"deliveryDays":r[7] or 3,"inStock":r[8],"notes":r[9] or ""} for r in rows]

@app.post("/supplier-catalog")
def create_supplier_catalog(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO supplier_catalog (supplier_id,supplier_name,material_name,unit,price,min_quantity,delivery_days,in_stock,notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("supplierId"),data.get("supplierName",""),data.get("materialName",""),data.get("unit","шт"),data.get("price",0),data.get("minQuantity",1),data.get("deliveryDays",3),data.get("inStock",True),data.get("notes","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.put("/supplier-catalog/{id}")
def update_supplier_catalog(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE supplier_catalog SET price=%s,in_stock=%s,delivery_days=%s,notes=%s WHERE id=%s",
        (data.get("price",0),data.get("inStock",True),data.get("deliveryDays",3),data.get("notes",""),id))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.delete("/supplier-catalog/{id}")
def delete_supplier_catalog(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM supplier_catalog WHERE id=%s",(id,))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.put("/suppliers/{id}/requisites")
def update_supplier_requisites(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""UPDATE suppliers SET 
        inn=%s, kpp=%s, legal_address=%s, bank=%s, bik=%s, account=%s,
        phone=COALESCE(%s, phone), email=COALESCE(%s, email)
        WHERE id=%s""",
        (data.get("inn",""), data.get("kpp",""), data.get("address",""),
         data.get("bank",""), data.get("bik",""), data.get("account",""),
         data.get("phone") or None, data.get("email") or None, id))
    conn.commit()
    cur.close(); conn.close()
    return {"ok": True}

@app.get("/warehouse-invoices")
def get_warehouse_invoices():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,number,date,supplier_id,supplier_name,accepted_by,location,project,vat,items,total_base,total_vat,total_with_vat,status,added_by,photo_url FROM warehouse_invoices ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    import json as j
    result = []
    for r in rows:
        try: items = j.loads(r[9]) if r[9] else []
        except: items = []
        result.append({"id":r[0],"number":r[1],"date":str(r[2]) if r[2] else "","supplierId":r[3],"supplierName":r[4] or "","acceptedBy":r[5] or "","location":r[6] or "","project":r[7] or "","vat":r[8] or "Без НДС","items":items,"totalBase":float(r[10] or 0),"totalVat":float(r[11] or 0),"totalWithVat":float(r[12] or 0),"status":r[13] or "Принята","addedBy":r[14] or "","photoUrl":r[15] or ""})
    return result

@app.post("/warehouse-invoices")
def create_warehouse_invoice(data: dict):
    import json as j
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO warehouse_invoices (number,date,supplier_id,supplier_name,accepted_by,location,project,vat,items,total_base,total_vat,total_with_vat,status,added_by,photo_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("number",""),data.get("date") or None,data.get("supplierId") or None,data.get("supplierName",""),data.get("acceptedBy",""),data.get("location",""),data.get("project",""),data.get("vat","Без НДС"),j.dumps(data.get("items",[]),ensure_ascii=False),data.get("totalBase",0),data.get("totalVat",0),data.get("totalWithVat",0),data.get("status","Принята"),data.get("addedBy",""),data.get("photoUrl","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.delete("/warehouse-invoices/{id}")
def delete_warehouse_invoice(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM warehouse_invoices WHERE id=%s",(id,))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

# Хранилище онлайн статусов
online_users = {}

@app.post("/online")
def update_online(data: dict):
    user_id = data.get("userId")
    if user_id:
        online_users[str(user_id)] = {
            "userId": user_id,
            "userName": data.get("userName",""),
            "userRole": data.get("userRole",""),
            "lastSeen": data.get("lastSeen",""),
            "page": data.get("page","")
        }
    return {"ok": True}

@app.get("/online")
def get_online():
    import time
    now = time.time()
    # Возвращаем пользователей активных за последние 2 минуты
    return list(online_users.values())

@app.get("/project-payments")
def get_project_payments(project_name: str = ""):
    conn = get_db()
    cur = conn.cursor()
    if project_name:
        cur.execute("SELECT id,project_name,amount,note,date,added_by FROM project_payments WHERE project_name=%s ORDER BY id DESC", (project_name,))
    else:
        cur.execute("SELECT id,project_name,amount,note,date,added_by FROM project_payments ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"projectName":r[1],"amount":float(r[2] or 0),"note":r[3] or "","date":str(r[4]) if r[4] else "","addedBy":r[5] or ""} for r in rows]

@app.post("/project-payments")
def create_project_payment(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO project_payments (project_name,amount,note,date,added_by) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (data.get("projectName",""),data.get("amount",0),data.get("note",""),data.get("date") or None,data.get("addedBy","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

VK_TOKEN = "vk1.a.aBp-tPMNFw5HSZhCUESCIw-H8T4cmSpYIryHHbmGfy67n8dNoIbuD3jbQ6"

def send_vk_notification(vk_user_id: int, message: str):
    import requests
    try:
        requests.post("https://api.vk.com/method/messages.send", params={
            "user_id": vk_user_id,
            "message": message,
            "random_id": 0,
            "access_token": VK_TOKEN,
            "v": "5.131"
        }, timeout=5)
    except Exception as e:
        print("VK error:", e)

@app.post("/vk-connect")
def vk_connect(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS vk_id INTEGER")
    cur.execute("UPDATE users SET vk_id=%s WHERE email=%s", (data.get("vkId"), data.get("email")))
    conn.commit()
    cur.close(); conn.close()
    return {"ok": True}

@app.post("/vk-notify")
def vk_notify(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT vk_id FROM users WHERE id=%s", (data.get("userId"),))
    row = cur.fetchone()
    cur.close(); conn.close()
    if row and row[0]:
        send_vk_notification(row[0], data.get("message",""))
    return {"ok": True}

@app.get("/accountable-payments")
def get_accountable_payments(project_name: str = ""):
    conn = get_db()
    cur = conn.cursor()
    if project_name:
        cur.execute("SELECT id,project_name,given_to,amount,payment_method,purpose,date,added_by,status,spent_amount FROM accountable_payments WHERE project_name=%s ORDER BY id DESC", (project_name,))
    else:
        cur.execute("SELECT id,project_name,given_to,amount,payment_method,purpose,date,added_by,status,spent_amount FROM accountable_payments ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"projectName":r[1],"givenTo":r[2],"amount":float(r[3] or 0),"paymentMethod":r[4] or "Наличные","purpose":r[5] or "","date":str(r[6]) if r[6] else "","addedBy":r[7] or "","status":r[8] or "Открыт","spentAmount":float(r[9] or 0)} for r in rows]

@app.post("/accountable-payments")
def create_accountable_payment(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO accountable_payments (project_name,given_to,given_to_id,amount,payment_method,purpose,date,added_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("projectName",""),data.get("givenTo",""),data.get("givenToId"),data.get("amount",0),data.get("paymentMethod","Наличные"),data.get("purpose",""),data.get("date") or None,data.get("addedBy","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.get("/accountable-expenses")
def get_accountable_expenses(payment_id: int = 0):
    conn = get_db()
    cur = conn.cursor()
    if payment_id:
        cur.execute("SELECT id,payment_id,project_name,description,amount,photo_url,date,added_by FROM accountable_expenses WHERE payment_id=%s ORDER BY id DESC", (payment_id,))
    else:
        cur.execute("SELECT id,payment_id,project_name,description,amount,photo_url,date,added_by FROM accountable_expenses ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"paymentId":r[1],"projectName":r[2],"description":r[3],"amount":float(r[4] or 0),"photoUrl":r[5] or "","date":str(r[6]) if r[6] else "","addedBy":r[7] or ""} for r in rows]

@app.post("/accountable-expenses")
def create_accountable_expense(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO accountable_expenses (payment_id,project_name,description,amount,photo_url,date,added_by) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("paymentId"),data.get("projectName",""),data.get("description",""),data.get("amount",0),data.get("photoUrl",""),data.get("date") or None,data.get("addedBy","")))
    # Обновляем spent_amount
    cur.execute("UPDATE accountable_payments SET spent_amount=spent_amount+%s WHERE id=%s", (data.get("amount",0),data.get("paymentId")))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}
    return {"id":row[0],"ok":True}

@app.get("/own-expenses")
def get_own_expenses(project_name: str = "", employee_name: str = ""):
    conn = get_db()
    cur = conn.cursor()
    if project_name:
        cur.execute("SELECT id,project_name,employee_name,description,amount,photo_url,date,status,approved_by FROM own_expenses WHERE project_name=%s ORDER BY id DESC", (project_name,))
    elif employee_name:
        cur.execute("SELECT id,project_name,employee_name,description,amount,photo_url,date,status,approved_by FROM own_expenses WHERE employee_name=%s ORDER BY id DESC", (employee_name,))
    else:
        cur.execute("SELECT id,project_name,employee_name,description,amount,photo_url,date,status,approved_by FROM own_expenses ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"projectName":r[1],"employeeName":r[2],"description":r[3],"amount":float(r[4] or 0),"photoUrl":r[5] or "","date":str(r[6]) if r[6] else "","status":r[7] or "Ожидает","approvedBy":r[8] or ""} for r in rows]

@app.post("/own-expenses")
def create_own_expense(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO own_expenses (project_name,employee_name,employee_id,description,amount,photo_url,date) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (data.get("projectName",""),data.get("employeeName",""),data.get("employeeId"),data.get("description",""),data.get("amount",0),data.get("photoUrl",""),data.get("date") or None))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.put("/own-expenses/{id}")
def update_own_expense(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE own_expenses SET status=%s,approved_by=%s WHERE id=%s",
        (data.get("status","Ожидает"),data.get("approvedBy",""),id))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.get("/expenses")
def get_expenses(project: str = ""):
    conn = get_db()
    cur = conn.cursor()
    if project:
        cur.execute("SELECT id,project,category,amount,note,date,added_by FROM expenses WHERE project=%s ORDER BY id DESC", (project,))
    else:
        cur.execute("SELECT id,project,category,amount,note,date,added_by FROM expenses ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"project":r[1],"category":r[2],"amount":float(r[3] or 0),"note":r[4] or "","date":str(r[5]) if r[5] else "","addedBy":r[6] or ""} for r in rows]

@app.post("/expenses")
def create_expense(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO expenses (project,category,amount,note,date,added_by) VALUES (%s,%s,%s,%s,%s,%s)",
        (data.get("project",""),data.get("category","other"),data.get("amount",0),data.get("note",""),data.get("date") or None,data.get("addedBy","")))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

@app.get("/project-ai-summary/{project_name}")
def get_project_ai_summary(project_name: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT payload_hash, summary, updated_at FROM project_ai_summary WHERE project_name=%s", (project_name,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        return {"exists": False}
    return {"exists": True, "payloadHash": row[0], "summary": row[1] or "", "updatedAt": str(row[2])}

@app.post("/project-ai-summary")
def save_project_ai_summary(data: dict):
    project_name = data.get("projectName", "")
    if not project_name:
        raise HTTPException(status_code=400, detail="projectName required")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO project_ai_summary (project_name, payload_hash, summary, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (project_name) DO UPDATE SET
            payload_hash = EXCLUDED.payload_hash,
            summary = EXCLUDED.summary,
            updated_at = NOW()
    """, (project_name, data.get("payloadHash", ""), data.get("summary", "")))
    conn.commit()
    cur.close(); conn.close()
    return {"ok": True}

@app.post("/ai-generate-estimate")
def ai_generate_estimate(data: dict):
    import openai as oa
    import json as _json
    description = (data.get("description") or "").strip()
    project_id = data.get("projectId")
    pricelist_id = data.get("pricelistId")
    name_hint = (data.get("name") or "Сгенерированная смета").strip()
    area = data.get("area")
    if not description:
        raise HTTPException(status_code=400, detail="Опишите объект — поле обязательно")

    conn = get_db()
    cur = conn.cursor()

    pricelist_items = []
    project_name = ""
    if project_id:
        try:
            cur.execute("SELECT name, pricelist_id FROM projects WHERE id=%s", (int(project_id),))
            r = cur.fetchone()
            if r:
                project_name = r[0] or ""
                if not pricelist_id and r[1]:
                    pricelist_id = r[1]
        except Exception:
            pass
    if pricelist_id:
        cur.execute("SELECT id, name, unit, price, category FROM pricelist_items WHERE pricelist_id=%s ORDER BY category, name LIMIT 400", (int(pricelist_id),))
        pricelist_items = [{"id": r[0], "name": r[1], "unit": r[2], "price": float(r[3] or 0), "category": r[4] or ""} for r in cur.fetchall()]

    parts = []
    parts.append("Ты опытный сметчик. Составь смету для объекта на основе описания. ВЕРНИ СТРОГО ВАЛИДНЫЙ JSON без markdown.")
    parts.append("\nОПИСАНИЕ ОБЪЕКТА:\n" + description)
    if area:
        parts.append("Площадь: " + str(area) + " м²")
    if project_name:
        parts.append("Проект: " + project_name)
    if pricelist_items:
        parts.append("\nИспользуй ТОЛЬКО позиции из этого прайс-листа (поле name копируй точно):")
        for it in pricelist_items:
            parts.append("- ["+str(it["category"])+"] "+it["name"]+" — "+it["unit"]+" — "+str(int(it["price"]))+"₽")
    else:
        parts.append("\nПрайс-листа нет — используй типовые работы и материалы для подобных объектов с рыночными ценами по РФ 2026.")

    parts.append("""
ФОРМАТ ОТВЕТА — ровно такой JSON:
{
  "name": "название сметы одной строкой",
  "sections": [
    {"name": "Раздел 1. ...", "items": [
      {"name": "...", "unit": "м2|шт|кг|...", "quantity": число, "priceWork": число, "priceMaterial": число, "itemType": "work" или "material"}
    ]}
  ]
}

ПРАВИЛА:
1. Раздели смету на 4-8 разделов по этапам работ (демонтаж, основание, отделка, сантехника и т.д.).
2. В каждом разделе сначала идут работы (itemType="work" с priceWork>0, priceMaterial=0), затем материалы (itemType="material" с priceMaterial>0, priceWork=0).
3. Объёмы (quantity) прикинь реалистично по площади и описанию.
4. Если в прайсе нет нужной позиции — добавь её всё равно (только в крайнем случае) с рыночной ценой.
5. Числа БЕЗ пробелов и валюты — только цифры. quantity может быть дробным.
6. ТОЛЬКО валидный JSON. Никакого текста до или после.""")
    full_prompt = "\n".join(parts)

    instructions = "Ты отвечаешь СТРОГО валидным JSON. Никакого markdown, ```, никакого текста до или после JSON. Только сам JSON."

    client = oa.OpenAI(api_key=YANDEX_API_KEY, base_url="https://ai.api.cloud.yandex.net/v1", project=YANDEX_FOLDER_ID)
    try:
        response = client.responses.create(
            model="gpt://" + YANDEX_FOLDER_ID + "/qwen3.6-35b-a3b/latest",
            temperature=0.2,
            instructions=instructions,
            input=full_prompt,
            max_output_tokens=6000,
        )
        raw = (response.output_text or "").strip()
    except Exception as e:
        cur.close(); conn.close()
        print("AI-GENERATE EXCEPTION:", str(e))
        raise HTTPException(status_code=500, detail="Ошибка ИИ: " + str(e))

    print("AI-GENERATE RAW LEN:", len(raw))
    print("AI-GENERATE RAW HEAD:", raw[:300])
    print("AI-GENERATE RAW TAIL:", raw[-300:] if len(raw) > 300 else "")

    import re as _re
    clean = raw.strip()
    clean = _re.sub(r"^```(?:json|JSON)?\s*", "", clean)
    clean = _re.sub(r"\s*```\s*$", "", clean)
    clean = clean.strip()

    s_idx = clean.find("{")
    e_idx = clean.rfind("}")
    parsed = None
    parse_error = None
    if s_idx >= 0 and e_idx > s_idx:
        candidate = clean[s_idx:e_idx + 1]
        try:
            parsed = _json.loads(candidate)
        except Exception as pe:
            parse_error = str(pe)
            # Trailing-junk fallback: cut from the last } backwards
            for cut in range(e_idx, s_idx, -1):
                if clean[cut] == "}":
                    try:
                        parsed = _json.loads(clean[s_idx:cut + 1])
                        parse_error = None
                        break
                    except Exception:
                        continue

    if not parsed or not isinstance(parsed.get("sections"), list):
        cur.close(); conn.close()
        print("AI-GENERATE PARSE FAILED. parse_error:", parse_error)
        raise HTTPException(status_code=500, detail="Не удалось распознать ответ ИИ как JSON. Попробуйте ещё раз или измените описание. Подробности в логах backend.")

    sections = []
    import time as _time
    for i, s in enumerate(parsed.get("sections") or []):
        items = []
        for j, it in enumerate(s.get("items") or []):
            items.append({
                "id": int(_time.time()*1000) + i*100 + j,
                "name": str(it.get("name") or ""),
                "unit": str(it.get("unit") or "шт"),
                "quantity": float(it.get("quantity") or 0),
                "priceWork": float(it.get("priceWork") or 0),
                "priceMaterial": float(it.get("priceMaterial") or 0),
                "itemType": str(it.get("itemType") or ("material" if float(it.get("priceMaterial") or 0) > 0 and float(it.get("priceWork") or 0) == 0 else "work")),
            })
        sections.append({"id": int(_time.time()*1000) + i, "name": str(s.get("name") or ("Раздел " + str(i+1))), "items": items})

    final_name = (parsed.get("name") or name_hint or "Сгенерированная смета")
    cur.execute("INSERT INTO estimates (project_id, project_name, name, version, sections_json) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (int(project_id) if project_id else None, project_name, final_name, "1.0", _json.dumps(sections, ensure_ascii=False)))
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); conn.close()

    return {"ok": True, "id": new_id, "name": final_name, "projectId": project_id, "projectName": project_name, "sections": sections}

@app.post("/pricelists/from-estimate")
def pricelist_from_estimate(data: dict):
    import json as _json
    estimate_id = data.get("estimateId")
    name = (data.get("name") or "").strip()
    for_who = (data.get("forWho") or "").strip()
    coefficient = float(data.get("coefficient") or 1.0)
    if not estimate_id:
        raise HTTPException(status_code=400, detail="Выберите смету")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name, sections_json FROM estimates WHERE id=%s", (int(estimate_id),))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        raise HTTPException(status_code=404, detail="Смета не найдена")
    estimate_name = row[0] or ""
    try:
        sections = _json.loads(row[1]) if row[1] else []
    except Exception:
        sections = []

    final_name = name or ("Прайс из сметы — " + estimate_name)
    cur.execute("INSERT INTO pricelists (name, description, for_who, coefficient) VALUES (%s, %s, %s, %s) RETURNING id",
                (final_name, "Создан из сметы: " + estimate_name, for_who, coefficient))
    pricelist_id = cur.fetchone()[0]

    inserted = 0
    seen = set()
    for s in sections:
        category = str(s.get("name") or "")
        for it in (s.get("items") or []):
            nm = str(it.get("name") or "").strip()
            if not nm:
                continue
            key = (nm.lower(), category.lower())
            if key in seen:
                continue
            seen.add(key)
            unit = str(it.get("unit") or "шт")
            item_type = str(it.get("itemType") or "")
            try:
                price_work = float(it.get("priceWork") or 0)
                price_material = float(it.get("priceMaterial") or 0)
                qty = float(it.get("quantity") or 0)
            except Exception:
                price_work = price_material = qty = 0
            is_imported = bool(it.get("isImported"))
            if item_type == "material" or (price_material > 0 and price_work == 0):
                kind = "material"
                price = price_material if not is_imported or qty == 0 else (price_material / qty if qty > 0 else price_material)
            else:
                kind = "work"
                price = price_work if not is_imported or qty == 0 else (price_work / qty if qty > 0 else price_work)
            cur.execute("INSERT INTO pricelist_items (pricelist_id, name, unit, price, category, specialization, item_type) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (pricelist_id, nm, unit, round(price, 2), category, for_who, kind))
            inserted += 1

    conn.commit()
    cur.close(); conn.close()
    return {"ok": True, "id": pricelist_id, "name": final_name, "itemsCount": inserted}

@app.post("/ai-generate-pricelist")
def ai_generate_pricelist(data: dict):
    import openai as oa
    import json as _json
    description = (data.get("description") or "").strip()
    name_hint = (data.get("name") or "Прайс-лист (ИИ)").strip()
    for_who = (data.get("forWho") or "").strip()
    coefficient = float(data.get("coefficient") or 1.0)
    if not description:
        raise HTTPException(status_code=400, detail="Опишите для каких работ нужен прайс — поле обязательно")

    instructions = "Ты отвечаешь СТРОГО валидным JSON. Никакого markdown, ```, никакого текста до или после JSON. Только сам JSON."

    parts = []
    parts.append("Ты опытный сметчик. Составь прайс-лист с реалистичными рыночными ценами по РФ 2026.")
    parts.append("\nОПИСАНИЕ:\n" + description)
    if for_who:
        parts.append("Для специализации: " + for_who)
    parts.append("""
ФОРМАТ ОТВЕТА — ровно такой JSON:
{
  "name": "название прайс-листа",
  "items": [
    {"name": "название позиции", "unit": "м2|шт|кг|м|м.п.|т|...", "price": число, "category": "категория"}
  ]
}

ПРАВИЛА:
1. 25-60 позиций, охватывающих описание.
2. Группируй позиции по категориям ("Демонтаж","Стены","Полы","Потолок","Сантехника","Электрика","Отделка","Прочее" и т.д.).
3. Цены — за единицу (за м², за шт, за кг). Без пробелов, без валюты, только цифры. Дробные значения допускаются.
4. Если работа сложная — указывай отдельные позиции по этапам.
5. ТОЛЬКО валидный JSON, никакого текста до/после.""")
    full_prompt = "\n".join(parts)

    client = oa.OpenAI(api_key=YANDEX_API_KEY, base_url="https://ai.api.cloud.yandex.net/v1", project=YANDEX_FOLDER_ID)

    def _call(model_id):
        try:
            r = client.responses.create(
                model="gpt://" + YANDEX_FOLDER_ID + "/" + model_id,
                temperature=0.2,
                instructions=instructions,
                input=full_prompt,
                max_output_tokens=5000,
            )
            return (r.output_text or "").strip(), None
        except Exception as e:
            return "", str(e)

    raw, err = _call("qwen3.6-35b-a3b/latest")
    if not raw.strip():
        print("AI-PRICELIST PRIMARY EMPTY, err=" + str(err))
        raw, err = _call("yandexgpt-5.1/latest")
    print("AI-PRICELIST RAW LEN:", len(raw))
    print("AI-PRICELIST RAW HEAD:", raw[:300])
    if not raw.strip():
        raise HTTPException(status_code=500, detail="ИИ вернул пустой ответ. Попробуйте ещё раз.")

    import re as _re
    clean = raw.strip()
    clean = _re.sub(r"^```(?:json|JSON)?\s*", "", clean)
    clean = _re.sub(r"\s*```\s*$", "", clean)
    clean = clean.strip()
    s_idx = clean.find("{")
    e_idx = clean.rfind("}")
    parsed = None
    if s_idx >= 0 and e_idx > s_idx:
        candidate = clean[s_idx:e_idx + 1]
        try:
            parsed = _json.loads(candidate)
        except Exception:
            for cut in range(e_idx, s_idx, -1):
                if clean[cut] == "}":
                    try:
                        parsed = _json.loads(clean[s_idx:cut + 1])
                        break
                    except Exception:
                        continue
    if not parsed or not isinstance(parsed.get("items"), list) or not parsed.get("items"):
        print("AI-PRICELIST PARSE FAILED")
        raise HTTPException(status_code=500, detail="Не удалось распознать ответ ИИ как JSON. Попробуйте ещё раз или измените описание.")

    final_name = parsed.get("name") or name_hint
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO pricelists (name, description, for_who, coefficient) VALUES (%s, %s, %s, %s) RETURNING id",
                (final_name, description[:500], for_who, coefficient))
    pricelist_id = cur.fetchone()[0]
    inserted = 0
    for it in parsed.get("items") or []:
        nm = str(it.get("name") or "").strip()
        if not nm:
            continue
        unit = str(it.get("unit") or "шт")
        try:
            price = float(it.get("price") or 0)
        except Exception:
            price = 0
        category = str(it.get("category") or "")
        cur.execute("INSERT INTO pricelist_items (pricelist_id, name, unit, price, category, specialization) VALUES (%s, %s, %s, %s, %s, %s)",
                    (pricelist_id, nm, unit, price, category, for_who))
        inserted += 1
    conn.commit()
    cur.close(); conn.close()

    return {"ok": True, "id": pricelist_id, "name": final_name, "itemsCount": inserted}

@app.get("/estimates/{estimate_id}/chat-history")
def get_estimate_chat(estimate_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, role, content, created_at FROM estimate_chat_messages WHERE estimate_id=%s ORDER BY id ASC", (estimate_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id": r[0], "role": r[1], "content": r[2], "createdAt": str(r[3])} for r in rows]

@app.post("/estimate-chat")
def estimate_chat(data: dict):
    import openai as oa
    estimate_id = data.get("estimateId")
    user_message = (data.get("message") or "").strip()
    context = (data.get("context") or "").strip()
    history = data.get("history") or []
    if not estimate_id or not user_message:
        raise HTTPException(status_code=400, detail="estimateId and message required")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO estimate_chat_messages (estimate_id, role, content) VALUES (%s, %s, %s) RETURNING id, created_at",
                (estimate_id, "user", user_message))
    user_row = cur.fetchone()
    conn.commit()

    prompt_lines = []
    if context:
        prompt_lines.append("КОНТЕКСТ СМЕТЫ:\n" + context)
    if history:
        prompt_lines.append("\nПРЕДЫДУЩИЙ ДИАЛОГ:")
        for m in history[-20:]:
            r = m.get("role", "user")
            c = m.get("content", "")
            prompt_lines.append(("Пользователь: " if r == "user" else "Ассистент: ") + c)
    prompt_lines.append("\nНОВЫЙ ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n" + user_message)
    prompt_lines.append("\nОтветь по-русски, используя факты из контекста сметы. Если для ответа недостаточно данных — скажи об этом. Если вопрос требует расчёта — приведи цифры явно.")
    full_prompt = "\n".join(prompt_lines)

    instructions = "Ты эксперт по строительным сметам. Помогаешь анализировать конкретную смету в формате диалога. Отвечаешь только по данной смете, не выдумываешь позиции. Используй конкретные числа из контекста."

    client = oa.OpenAI(api_key=YANDEX_API_KEY, base_url="https://ai.api.cloud.yandex.net/v1", project=YANDEX_FOLDER_ID)
    try:
        response = client.responses.create(
            model="gpt://" + YANDEX_FOLDER_ID + "/yandexgpt-5.1/latest",
            temperature=0.3,
            instructions=instructions,
            input=full_prompt,
            max_output_tokens=1500,
        )
        answer = response.output_text or ""
    except Exception as e:
        answer = "Ошибка ИИ: " + str(e)

    cur.execute("INSERT INTO estimate_chat_messages (estimate_id, role, content) VALUES (%s, %s, %s) RETURNING id, created_at",
                (estimate_id, "assistant", answer))
    asst_row = cur.fetchone()
    conn.commit()
    cur.close(); conn.close()
    return {"response": answer, "userMessageId": user_row[0], "assistantMessageId": asst_row[0]}

@app.delete("/estimates/{estimate_id}/chat-history")
def clear_estimate_chat(estimate_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM estimate_chat_messages WHERE estimate_id=%s", (estimate_id,))
    conn.commit()
    cur.close(); conn.close()
    return {"ok": True}

@app.post("/scan-invoice")
def scan_invoice(data: dict):
    import openai as oa
    FOLDER_ID = YANDEX_FOLDER_ID
    API_KEY = YANDEX_API_KEY
    base64_image = data.get("image", "")
    client = oa.OpenAI(api_key=API_KEY, base_url="https://ai.api.cloud.yandex.net/v1", project=FOLDER_ID)
    try:
        response = client.responses.create(
            model=f"gpt://{FOLDER_ID}/qwen3.6-35b-a3b/latest",
            temperature=0.1,
            instructions="Ты распознаёшь накладные. Верни только JSON без комментариев и без markdown.",
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{base64_image}"},
                        {"type": "input_text", "text": "Распознай накладную. Верни JSON: {supplier:строка, items:[{name:строка,quantity:число,unit:строка,price:число}], total:число}. Только JSON без комментариев."}
                    ]
                }
            ],
            max_output_tokens=1000
        )
        answer = response.output_text
        import json
        clean = answer.replace("```json","").replace("```","").strip()
        parsed = json.loads(clean)
        print("SCAN OK:", parsed)
        return {"ok": True, "data": parsed}
    except Exception as e:
        print("SCAN ERROR:", str(e))
        return {"ok": False, "error": str(e)}
