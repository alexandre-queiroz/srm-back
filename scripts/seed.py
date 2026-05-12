"""
Seed inicial: product_types, system_params e usuário admin.

Uso:
    python scripts/seed.py
    python scripts/seed.py --reset   # apaga e recria os registros
"""

import argparse
import sys
from decimal import Decimal

sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.product_type import ProductType
from app.models.system_param import SystemParam
from app.models.user import User

PRODUCT_TYPES = [
    {"name": "NF-e Mercantil", "spread": Decimal("0.02500000")},
    {"name": "NF-e Serviço", "spread": Decimal("0.03000000")},
    {"name": "NFS-e", "spread": Decimal("0.03500000")},
    {"name": "Duplicata Mercantil", "spread": Decimal("0.02000000")},
    {"name": "CTE", "spread": Decimal("0.02800000")},
]

SYSTEM_PARAMS = [
    {
        "key": "base_rate_annual",
        "value": Decimal("0.13750000"),
        "description": "Taxa Selic anualizada (referência CDI)",
    },
]

ADMIN_USER = {
    "email": "admin@srm.com.br",
    "password": "Admin@2026",
    "name": "Administrador SRM",
}


def seed(reset: bool = False) -> None:
    db = SessionLocal()
    try:
        if reset:
            db.query(ProductType).delete()
            db.query(SystemParam).delete()
            db.query(User).filter(User.email == ADMIN_USER["email"]).delete()
            db.commit()
            print("Registros anteriores removidos.")

        for pt in PRODUCT_TYPES:
            exists = db.query(ProductType).filter(ProductType.name == pt["name"]).first()
            if not exists:
                db.add(ProductType(**pt))
                print(f"  + ProductType: {pt['name']}")

        for sp in SYSTEM_PARAMS:
            exists = db.query(SystemParam).filter(SystemParam.key == sp["key"]).first()
            if not exists:
                db.add(SystemParam(**sp))
                print(f"  + SystemParam: {sp['key']} = {sp['value']}")

        exists = db.query(User).filter(User.email == ADMIN_USER["email"]).first()
        if not exists:
            db.add(
                User(
                    email=ADMIN_USER["email"],
                    password_hash=hash_password(ADMIN_USER["password"]),
                    name=ADMIN_USER["name"],
                    is_active=True,
                )
            )
            print(f"  + User: {ADMIN_USER['email']}")

        db.commit()
        print("Seed concluído.")
    except Exception as e:
        db.rollback()
        print(f"Erro: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Remove registros existentes antes de inserir")
    args = parser.parse_args()
    seed(reset=args.reset)
