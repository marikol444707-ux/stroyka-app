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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "dbname": "stroyka",
    "user": "nikolas",
    "password": "password",
    "host": "localhost",
    "port": "5432"
}

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
    cur.execute("SELECT id,name,client,status,budget,deadline,progress,tasks,pricelist_id as \"pricelistId\" FROM projects")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/projects")
def create_project(p: ProjectModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO projects (name,client,status,budget,deadline,progress,tasks,pricelist_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,name,client,status,budget,deadline,progress,tasks,pricelist_id as \"pricelistId\"",
                (p.name,p.client,p.status,p.budget,p.deadline,p.progress,p.tasks,p.pricelistId))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/projects/{id}")
def update_project(id: int, p: ProjectModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE projects SET name=%s,client=%s,status=%s,budget=%s,deadline=%s,progress=%s,tasks=%s,pricelist_id=%s WHERE id=%s",
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

@app.get("/staff")
def get_staff():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id,name,role,phone,salary,project,pay_type as \"payType\" FROM staff")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/staff")
def create_staff(s: StaffModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO staff (name,role,phone,salary,project,pay_type) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id,name,role,phone,salary,project,pay_type as \"payType\"",
                (s.name,s.role,s.phone,s.salary,s.project,s.payType))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/staff/{id}")
def update_staff(id: int, s: StaffModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE staff SET name=%s,role=%s,phone=%s,salary=%s,project=%s,pay_type=%s WHERE id=%s",
                (s.name,s.role,s.phone,s.salary,s.project,s.payType,id))
    conn.close()
    return {"ok": True}

@app.delete("/staff/{id}")
def delete_staff(id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM staff WHERE id=%s", (id,))
    conn.close()
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
    cur.execute("SELECT id,master_id as \"masterId\",master_name as \"masterName\",project,description,unit,quantity,price_per_unit as \"pricePerUnit\",total,date,status,comment,photo_url as \"photoUrl\",confirmed_by as \"confirmedBy\",confirmed_at as \"confirmedAt\" FROM work_journal ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/work-journal")
def create_work_journal(w: WorkJournalModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO work_journal (master_id,master_name,project,description,unit,quantity,price_per_unit,total,date,comment,photo_url) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (w.masterId,w.masterName,w.project,w.description,w.unit,w.quantity,w.pricePerUnit,w.total,w.date,w.comment,w.photoUrl))
    row = cur.fetchone()
    conn.close()
    return dict(row)

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
    cur.execute("SELECT id,project,name,floor_area as \"floorArea\",wall_area as \"wallArea\",ceiling_area as \"ceilingArea\",windows,doors,notes FROM rooms ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/rooms")
def create_room(r: RoomModel):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("INSERT INTO rooms (project,name,floor_area,wall_area,ceiling_area,windows,doors,notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id,project,name,floor_area as \"floorArea\",wall_area as \"wallArea\",ceiling_area as \"ceilingArea\",windows,doors,notes",
                (r.project,r.name,r.floorArea,r.wallArea,r.ceilingArea,r.windows,r.doors,r.notes))
    row = cur.fetchone()
    conn.close()
    return dict(row)

@app.put("/rooms/{id}")
def update_room(id: int, r: RoomModel):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE rooms SET project=%s,name=%s,floor_area=%s,wall_area=%s,ceiling_area=%s,windows=%s,doors=%s,notes=%s WHERE id=%s",
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
    import json as j
    messages = data.get("messages", [])
    last_msg = messages[-1].get("content","").lower() if messages else ""
    
    conn = get_db()
    cur = conn.cursor()
    
    # Проекты
    cur.execute("SELECT name, status, budget, progress FROM projects")
    projects = cur.fetchall()
    
    # Склад
    cur.execute("SELECT name, quantity, unit FROM warehouse_main")
    materials = cur.fetchall()
    
    # Сотрудники
    cur.execute("SELECT name, role FROM staff")
    staff = cur.fetchall()
    
    # Договора
    cur.execute("SELECT client, total_amount, status FROM contracts")
    contracts = cur.fetchall()
    
    # Наряды
    cur.execute("SELECT project_name, brigade_name, status, total_amount FROM brigade_contracts")
    brigades = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # Анализируем вопрос и формируем ответ
    response = ""
    
    # Проекты
    if any(w in last_msg for w in ["проект", "объект", "стройк"]):
        active = [p for p in projects if p[1] in ["В работе", "Активный"]]
        done = [p for p in projects if p[1] in ["Завершён", "Сдан"]]
        response = f"📋 Всего проектов: {len(projects)}\n"
        response += f"🔨 В работе: {len(active)}\n"
        response += f"✅ Завершено: {len(done)}\n"
        if projects:
            response += "\nПроекты:\n"
            for p in projects[:5]:
                response += f"• {p[0]} — {p[1]}"
                if p[2]: response += f" (бюджет: {int(p[2]):,} ₽)"
                response += "\n"
    
    # Склад/материалы
    elif any(w in last_msg for w in ["склад", "материал", "остаток", "запас"]):
        response = f"📦 На складе {len(materials)} позиций:\n\n"
        for m in materials[:10]:
            response += f"• {m[0]}: {m[1]} {m[2]}\n"
        if len(materials) > 10:
            response += f"\n...и ещё {len(materials)-10} позиций"
    
    # Сотрудники
    elif any(w in last_msg for w in ["сотрудник", "работник", "персонал", "штат", "кто"]):
        response = f"👷 Сотрудников: {len(staff)}\n\n"
        for s in staff[:8]:
            response += f"• {s[0]} — {s[1]}\n"
    
    # Договора/финансы
    elif any(w in last_msg for w in ["договор", "деньг", "финанс", "сумм", "оплат"]):
        total = sum(float(c[2] or 0) for c in contracts)
        active_c = [c for c in contracts if c[2] not in ["Расторгнут"]]
        response = f"💰 Договоров: {len(contracts)}\n"
        response += f"📄 Активных: {len(active_c)}\n"
        response += f"💵 Общая сумма: {total:,.0f} ₽\n\n"
        for c in contracts[:5]:
            response += f"• {c[0]} — {float(c[2] or 0):,.0f} ₽ ({c[1]})\n"
    
    # Наряды/бригады
    elif any(w in last_msg for w in ["наряд", "бригад", "подрядчик", "мастер"]):
        response = f"👷 Нарядов: {len(brigades)}\n\n"
        for b in brigades[:8]:
            response += f"• {b[1]} на объекте {b[0]} — {b[2]}\n"
    
    # Привет/помощь
    elif any(w in last_msg for w in ["привет", "помог", "что умеешь", "помощь"]):
        response = """Привет! Я ИИ помощник СтройКа 🤖

Я могу ответить на вопросы:
📋 О проектах и объектах
📦 Об остатках на складе  
👷 О сотрудниках и бригадах
💰 О договорах и финансах
📊 О нарядах и выполнении

Просто спросите!"""
    
    # Итоговая сводка
    elif any(w in last_msg for w in ["сводк", "итог", "статус", "отчёт", "отчет", "обзор"]):
        active_p = len([p for p in projects if p[1] in ["В работе","Активный"]])
        response = f"""📊 Сводка по системе:

🏗️ Проектов в работе: {active_p} из {len(projects)}
👷 Сотрудников: {len(staff)}
📦 Позиций на складе: {len(materials)}
📄 Договоров: {len(contracts)}
🔨 Нарядов бригадам: {len(brigades)}"""
    
    else:
        response = f"""Понял ваш вопрос! 

Вот что я знаю о вашей системе:
• Проектов: {len(projects)}
• Сотрудников: {len(staff)}  
• Материалов на складе: {len(materials)} позиций
• Договоров: {len(contracts)}

Уточните вопрос — спросите про проекты, склад, сотрудников, договора или наряды."""
    
    return {"response": response}


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
        current_item = None
        
        for row in ws.iter_rows(min_row=40, values_only=True):
            try:
                col1 = row[0] if len(row) > 0 else None
                col3 = row[2] if len(row) > 2 else None
                col8 = row[7] if len(row) > 7 else None
                col9 = row[8] if len(row) > 8 else None
                col16 = row[15] if len(row) > 15 else None
            except:
                continue
            
            if col1 and isinstance(col1, str) and "Раздел" in col1:
                current_section = col1.strip()
                continue
            
            if col3 is None:
                continue
            
            col3_str = str(col3).strip()
            
            if col1 is not None and col8 is not None and col3_str and len(col3_str) > 10:
                try:
                    num = int(float(str(col1)))
                    current_item = {
                        "section": current_section,
                        "num": num,
                        "name": col3_str,
                        "unit": str(col8) if col8 else "",
                        "quantity": float(col9) if col9 else 0,
                        "total": 0
                    }
                except:
                    pass
            
            if col3_str == "Всего по позиции" and current_item and col16:
                try:
                    current_item["total"] = float(col16)
                    # Фильтруем ненормируемые и служебные позиции
                    skip_words = ["ненормируемые", "накладные расходы", "сметная прибыль", "временные здания"]
                    if not any(w in current_item["name"].lower() for w in skip_words) and current_item["unit"] != "%":
                        results.append(dict(current_item))
                except:
                    pass
                current_item = None
        
        os.unlink(tmp_path)
        return {"items": results, "count": len(results)}
    except Exception as e:
        os.unlink(tmp_path)
        return {"error": str(e)}

@app.get("/estimates")
def get_estimates():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,project_id,project_name,name,version,sections_json FROM estimates ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    import json as j
    result = []
    for r in rows:
        try:
            sections = j.loads(r[5]) if r[5] else []
        except:
            sections = []
        result.append({"id":r[0],"projectId":r[1],"projectName":r[2],"name":r[3],"version":r[4],"sections":sections})
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
    cur.execute("UPDATE estimates SET name=%s,version=%s,sections_json=%s WHERE id=%s",
        (data.get("name",""),data.get("version","1.0"),j.dumps(data.get("sections",[]),ensure_ascii=False),id))
    conn.commit()
    cur.close(); conn.close()
    return {"ok":True}

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
        cur.execute("SELECT id,project_id,project_name,brigade_name,contractor_type,contractor_id,total_amount,status,signed_at,notes,created_at FROM brigade_contracts WHERE project_name=%s ORDER BY id DESC", (project_name,))
    else:
        cur.execute("SELECT id,project_id,project_name,brigade_name,contractor_type,contractor_id,total_amount,status,signed_at,notes,created_at FROM brigade_contracts ORDER BY id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"projectId":r[1],"projectName":r[2],"brigadeName":r[3],"contractorType":r[4],"contractorId":r[5],"totalAmount":float(r[6] or 0),"status":r[7],"signedAt":str(r[8]) if r[8] else "","notes":r[9] or "","createdAt":str(r[10])} for r in rows]

@app.post("/brigade-contracts")
def create_brigade_contract(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO brigade_contracts (project_id,project_name,brigade_name,contractor_type,contractor_id,total_amount,status,notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("projectId") or None,data.get("projectName",""),data.get("brigadeName",""),data.get("contractorType","Бригада"),data.get("contractorId") or None,data.get("totalAmount",0),data.get("status","Черновик"),data.get("notes","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.put("/brigade-contracts/{id}")
def update_brigade_contract(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE brigade_contracts SET brigade_name=%s,contractor_type=%s,total_amount=%s,status=%s,signed_at=%s,notes=%s WHERE id=%s",
        (data.get("brigadeName",""),data.get("contractorType","Бригада"),data.get("totalAmount",0),data.get("status","Черновик"),data.get("signedAt") or None,data.get("notes",""),id))
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

@app.get("/brigade-contract-items/{contract_id}")
def get_brigade_contract_items(contract_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id,contract_id,estimate_section,name,unit,quantity,price_smeta,price_brigade,done_quantity,status FROM brigade_contract_items WHERE contract_id=%s ORDER BY id", (contract_id,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id":r[0],"contractId":r[1],"estimateSection":r[2],"name":r[3],"unit":r[4],"quantity":float(r[5] or 0),"priceSmeta":float(r[6] or 0),"priceBrigade":float(r[7] or 0),"doneQuantity":float(r[8] or 0),"status":r[9]} for r in rows]

@app.post("/brigade-contract-items")
def create_brigade_contract_item(data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO brigade_contract_items (contract_id,estimate_section,name,unit,quantity,price_smeta,price_brigade,done_quantity,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("contractId"),data.get("estimateSection",""),data.get("name",""),data.get("unit",""),data.get("quantity",0),data.get("priceSmeta",0),data.get("priceBrigade",0),data.get("doneQuantity",0),data.get("status","Не начато")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

@app.put("/brigade-contract-items/{id}")
def update_brigade_contract_item(id: int, data: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE brigade_contract_items SET price_brigade=%s,done_quantity=%s,status=%s WHERE id=%s",
        (data.get("priceBrigade",0),data.get("doneQuantity",0),data.get("status","Не начато"),id))
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
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO material_transfers (project_name,from_location,to_person,to_person_role,material_name,quantity,unit,transfer_date,notes,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (data.get("projectName",""),data.get("fromLocation","Основной склад"),data.get("toPerson",""),data.get("toPersonRole",""),data.get("materialName",""),data.get("quantity",0),data.get("unit","шт"),data.get("transferDate") or None,data.get("notes",""),data.get("createdBy","")))
    conn.commit()
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"id":row[0],"ok":True}

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
