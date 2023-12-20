# classes for representing data are defined here
from uuid import uuid4
from werkzeug.security import generate_password_hash, check_password_hash
import enum
from dataclasses import dataclass, field

def gen_blank():
    return {}
def gen_uuid4():
    return str(uuid4())

@dataclass
class Product():
    name: str
    description: str
    brand: str
    quantity: int
    image_path: str
    msrp: float
    price: float
    supplier_uuid: str
    uuid: str = field(default_factory= gen_uuid4)
    total_orders = 0

@dataclass
class Customer:
    name: str
    email: str
    phonenumber: str
    password: str
    address: str
    reward_points: int = 100
    rewards: dict = field(default_factory= gen_blank)
    cart: dict = field(default_factory= gen_blank)
    orders: dict = field(default_factory= gen_blank)
    uuid: str = field(default_factory= gen_uuid4)

    def __post_init__(self):
        self.password = generate_password_hash(self.password)

    def check_password(self, p):
        return check_password_hash(self.password, p)

    

@dataclass
class CartItem:
    product_uuid: str
    quantity: int
    uuid: str = field(default_factory= gen_uuid4)


@dataclass
class Admin:
    name: str
    email: str
    password: str
    uuid: str = field(default_factory= gen_uuid4)

    def __post_init__(self):
        self.password = generate_password_hash(self.password)

    def check_password(self, p):
        return check_password_hash(self.password, p)

class OrderStatus(enum.Enum):
    APPROVAL_PENDING = "Approval Pending"
    SHIPPED = "Shipped"
    DELIVERED = "Delivered"
    REFUNDED = "Refunded"

class RewardStatus(enum.Enum):
    VALID = "Valid"
    INVALID = "Invalid"

@dataclass
class Order:
    product: Product
    quantity: int
    cost: float
    customer_uuid: str
    status: OrderStatus = OrderStatus.APPROVAL_PENDING
    uuid: str = field(default_factory= gen_uuid4)

@dataclass
class Reward:
    name: str
    cost: float
    percent_discount: float
    max_discount: float
    status: RewardStatus = RewardStatus.VALID
    uuid: str = field(default_factory= gen_uuid4)
    
    def calc_discount(self, total_amount: float):
        return round(min(self.max_discount, (self.percent_discount/100) * total_amount), 2)

    def flip(self):
        if self.status == RewardStatus.VALID:
            self.status = RewardStatus.INVALID
        else:
            self.status = RewardStatus.VALID

@dataclass
class Supplier:
    company: str
    address: str
    website: str
    phonenumber: str
    email: str
    uuid: str = field(default_factory= gen_uuid4)
