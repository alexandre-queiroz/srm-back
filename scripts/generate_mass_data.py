import argparse
import random
import sys
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.models.company import Company
from app.models.product_type import ProductType
from app.models.receivable import Receivable


def generate_cnpj():
    return "".join([str(random.randint(0, 9)) for _ in range(14)])


def generate_invoice_key():
    return "".join([str(random.randint(0, 9)) for _ in range(44)])


def generate_mass_data(num_assignors=5, num_drawees=20, num_receivables=200):
    db = SessionLocal()
    try:
        # 1. Ensure we have ProductTypes
        product_types = db.query(ProductType).all()
        if not product_types:
            print("Nenhum ProductType encontrado. Execute 'python scripts/seed.py' primeiro.")
            return

        # 2. Create Assignors
        assignors = []
        for i in range(num_assignors):
            name = f"Cedente {i + 1} Ltda"
            cnpj = generate_cnpj()
            company = db.query(Company).filter(Company.cnpj == cnpj).first()
            if not company:
                company = Company(name=name, cnpj=cnpj)
                db.add(company)
                db.flush()
            assignors.append(company)
        print(f"Instanciados {len(assignors)} cedentes.")

        # 3. Create Drawees
        drawees = []
        for i in range(num_drawees):
            name = f"Sacado {i + 1} S.A."
            cnpj = generate_cnpj()
            company = db.query(Company).filter(Company.cnpj == cnpj).first()
            if not company:
                company = Company(name=name, cnpj=cnpj)
                db.add(company)
                db.flush()
            drawees.append(company)
        print(f"Instanciados {len(drawees)} sacados.")

        # 4. Create Receivables
        count = 0
        for _ in range(num_receivables):
            assignor = random.choice(assignors)
            # Drawee must be different from assignor
            drawee = random.choice([d for d in drawees if d.id != assignor.id])
            product_type = random.choice(product_types)

            invoice_key = generate_invoice_key()
            invoice_number = str(random.randint(1000, 999999)).zfill(9)
            series = str(random.randint(1, 99)).zfill(3)
            issued_at = date.today() - timedelta(days=random.randint(1, 30))

            # Random installments
            num_installments = random.randint(1, 5)
            total_face_value = Decimal(str(random.uniform(1000, 50000))).quantize(Decimal("0.01"))

            for inst in range(1, num_installments + 1):
                face_value = (total_face_value / num_installments).quantize(Decimal("0.01"))
                due_date = issued_at + timedelta(days=30 * inst + random.randint(-5, 5))
                currency = random.choice(["BRL", "BRL", "BRL", "USD"])  # 25% chance of USD

                receivable = Receivable(
                    assignor_id=assignor.id,
                    drawee_id=drawee.id,
                    product_type_id=product_type.id,
                    invoice_key=invoice_key,
                    invoice_number=invoice_number,
                    series=series,
                    issued_at=issued_at,
                    installment_number=f"{inst}/{num_installments}",
                    products_value=face_value,
                    face_value=face_value,
                    currency_code=currency,
                    due_date=due_date,
                    status="available",
                )
                db.add(receivable)
                count += 1

        db.commit()
        print(f"Inseridos {count} recebíveis com sucesso.")

    except Exception as e:
        db.rollback()
        print(f"Erro ao gerar dados: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assignors", type=int, default=10)
    parser.add_argument("--drawees", type=int, default=50)
    parser.add_argument("--receivables", type=int, default=500)
    args = parser.parse_args()

    generate_mass_data(num_assignors=args.assignors, num_drawees=args.drawees, num_receivables=args.receivables)
