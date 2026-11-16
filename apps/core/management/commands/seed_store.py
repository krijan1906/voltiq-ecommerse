"""Seed a realistic Voltiq demo store.

Creates categories, brands, dynamic specification schemas, products with
images, verified demo accounts, stock history, orders, payments, reviews,
coupons, delivery methods, newsletter subscribers and contact messages.

The command is idempotent: re-running it updates catalogue content and skips
objects that already exist (orders are tracked by an internal seed marker).

Usage:
    python manage.py seed_store
    python manage.py seed_store --skip-images    # fastest, no downloads
"""
import io
import textwrap
from datetime import timedelta
from decimal import Decimal

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont

from apps.accounts.models import Address, CustomerProfile, Notification, User
from apps.categories.models import Brand, Category
from apps.core.models import ContactMessage, NewsletterSubscription, SiteSetting
from apps.inventory.models import StockHistory
from apps.orders.models import (
    Coupon,
    CouponUsage,
    Order,
    OrderItem,
    OrderStatusHistory,
    ShippingMethod,
    money,
)
from apps.payments.models import Payment
from apps.products.models import Product, ProductImage, ProductSpecification, SpecificationField
from apps.reviews.models import Review
from apps.wishlist.models import Wishlist, WishlistItem

DEMO_PASSWORD = "Customer@12345"
ADMIN_PASSWORD = "Admin@12345"
STAFF_PASSWORD = "Staff@12345"

# ---------------------------------------------------------------------------
# Catalogue structure
# ---------------------------------------------------------------------------
CATEGORIES = [
    ("Laptops", "laptop", None, "Ultrabooks, creator notebooks and gaming machines.", 1),
    ("Ultrabooks", "laptop", "Laptops", "Thin, light and all-day battery life.", 1),
    ("Gaming Laptops", "laptop", "Laptops", "High-refresh displays and discrete graphics.", 2),
    ("Smartphones", "smartphone", None, "Flagship and everyday phones with local warranty.", 2),
    ("Flagship Phones", "smartphone", "Smartphones", "The best cameras and displays available.", 1),
    ("Budget Phones", "smartphone", "Smartphones", "Great value without the flagship price.", 2),
    ("Audio", "headphones", None, "Headphones, earbuds and portable speakers.", 3),
    ("Headphones", "headphones", "Audio", "Over-ear listening for work and travel.", 1),
    ("Earbuds & Speakers", "headphones", "Audio", "True wireless earbuds and Bluetooth speakers.", 2),
    ("Gaming", "gamepad", None, "Consoles, controllers and competitive gear.", 4),
    ("Consoles", "gamepad", "Gaming", "Current-generation home consoles.", 1),
    ("Gaming Gear", "gamepad", "Gaming", "Keyboards, mice and desktop accessories.", 2),
    ("Monitors", "monitor", None, "Colour-accurate panels for work and play.", 5),
    ("Components", "cpu", None, "Graphics cards, storage and upgrade parts.", 6),
    ("Graphics Cards", "cpu", "Components", "GPUs for gaming, rendering and AI workloads.", 1),
    ("Storage & Memory", "chip", "Components", "NVMe drives, SSDs and memory upgrades.", 2),
    ("Wearables", "watch", None, "Smart watches and fitness trackers.", 7),
    ("Networking", "router", None, "Mesh Wi-Fi and home networking.", 8),
    ("Accessories", "package", None, "Everyday accessories that complete the setup.", 9),
    ("Keyboards & Mice", "keyboard", "Accessories", "Mechanical keyboards and precision mice.", 1),
    ("Power & Charging", "zap", "Accessories", "Fast chargers and high-capacity power banks.", 2),
]

BRANDS = [
    ("Apple", "https://www.apple.com"),
    ("Dell", "https://www.dell.com"),
    ("Asus", "https://www.asus.com"),
    ("Lenovo", "https://www.lenovo.com"),
    ("HP", "https://www.hp.com"),
    ("Samsung", "https://www.samsung.com"),
    ("Google", "https://store.google.com"),
    ("Xiaomi", "https://www.mi.com"),
    ("Sony", "https://www.sony.com"),
    ("JBL", "https://www.jbl.com"),
    ("Bose", "https://www.bose.com"),
    ("Microsoft", "https://www.microsoft.com"),
    ("Logitech", "https://www.logitech.com"),
    ("Razer", "https://www.razer.com"),
    ("LG", "https://www.lg.com"),
    ("NVIDIA", "https://www.nvidia.com"),
    ("TP-Link", "https://www.tp-link.com"),
    ("Anker", "https://www.anker.com"),
]

FIELD_SETS = {
    "Laptops": [
        ("Processor", "", "text", False),
        ("RAM", "GB", "text", True),
        ("Storage", "", "text", True),
        ("Graphics", "", "text", False),
        ("Display", "inches", "text", False),
        ("Operating system", "", "text", False),
    ],
    "Smartphones": [
        ("Processor", "", "text", False),
        ("RAM", "GB", "text", True),
        ("Storage", "GB", "text", True),
        ("Display", "inches", "text", False),
        ("Battery", "mAh", "number", False),
        ("Rear camera", "MP", "text", False),
    ],
    "Audio": [
        ("Driver size", "mm", "text", False),
        ("Battery life", "hours", "text", False),
        ("Connectivity", "", "text", True),
        ("Noise cancellation", "", "text", False),
    ],
    "Gaming": [
        ("Platform", "", "text", True),
        ("Storage", "GB", "text", False),
        ("Resolution", "", "text", False),
        ("Controller", "", "text", False),
    ],
    "Monitors": [
        ("Panel type", "", "text", True),
        ("Resolution", "", "text", True),
        ("Refresh rate", "Hz", "number", True),
        ("Screen size", "inches", "text", False),
    ],
    "Components": [
        ("Type", "", "text", False),
        ("Capacity", "", "text", True),
        ("Interface", "", "text", False),
        ("Memory type", "", "text", False),
    ],
    "Wearables": [
        ("Display", "", "text", False),
        ("Battery life", "hours", "text", False),
        ("Water resistance", "", "text", False),
        ("Connectivity", "", "text", True),
    ],
    "Networking": [
        ("Wi-Fi standard", "", "text", True),
        ("Coverage", "sq ft", "text", False),
        ("Ports", "", "text", False),
        ("Speed", "Mbps", "text", False),
    ],
    "Accessories": [
        ("Type", "", "text", True),
        ("Connectivity", "", "text", True),
        ("Battery life", "hours", "text", False),
        ("Weight", "g", "text", False),
    ],
}
CATEGORY_FIELD_OVERRIDES = {
    "Gaming Gear": [
        ("Type", "", "text", True),
        ("Connectivity", "", "text", True),
        ("Battery life", "hours", "text", False),
        ("Weight", "g", "text", False),
    ],
    "Keyboards & Mice": [
        ("Type", "", "text", True),
        ("Connectivity", "", "text", True),
        ("Battery life", "hours", "text", False),
        ("Weight", "g", "text", False),
    ],
    "Power & Charging": [
        ("Capacity", "mAh", "text", True),
        ("Output", "W", "text", True),
        ("Connector", "", "text", False),
        ("Compatibility", "", "text", False),
    ],
    "Consoles": [
        ("Platform", "", "text", True),
        ("Storage", "GB", "text", False),
        ("Resolution", "", "text", False),
        ("Controller", "", "text", False),
    ],
}

UNSPLASH = "https://images.unsplash.com/{photo}?auto=format&fit=crop&w=1200&q=80&fm=jpg"


def _product(
    name,
    sku,
    brand,
    category,
    price,
    cost,
    stock,
    short,
    description,
    highlights,
    specs,
    image,
    discount=None,
    threshold=5,
    featured=False,
    facets=None,
    condition="new",
):
    return {
        "name": name,
        "sku": sku,
        "brand": brand,
        "category": category,
        "price": price,
        "discount": discount,
        "cost": cost,
        "stock": stock,
        "threshold": threshold,
        "featured": featured,
        "short": short,
        "description": description,
        "highlights": highlights,
        "specs": specs,
        "image": UNSPLASH.format(photo=image),
        "facets": facets or {},
        "condition": condition,
    }


PRODUCTS = [
    _product(
        'MacBook Air 13" (M3)',
        "APL-MBA13-M3",
        "Apple",
        "Ultrabooks",
        189999,
        152000,
        12,
        "Apple M3, 16GB unified memory and 512GB SSD in a fanless 1.24kg chassis.",
        "The MacBook Air with M3 pairs a brilliant Liquid Retina display with silent, fanless performance. "
        "It is our pick for students, writers and developers who want all-day battery life without compromise.",
        [
            "Apple M3 chip with 8-core CPU and 10-core GPU",
            "Up to 18 hours of battery life",
            "13.6-inch Liquid Retina display with 500 nits",
            "Fanless design weighing just 1.24kg",
        ],
        [
            ("Processor", "Apple M3", ""),
            ("RAM", "16", "GB"),
            ("Storage", "512", "GB SSD"),
            ("Graphics", "Apple 10-core GPU", ""),
            ("Display", "13.6", "inches"),
            ("Operating system", "macOS Sonoma", ""),
        ],
        "photo-1517336714731-489689fd1ca8",
        discount=179999,
        featured=True,
        facets={
            "processor": "Apple M3",
            "ram": "16GB",
            "storage": "512GB",
            "gpu": "Apple 10-core GPU",
            "display_size": "13.6",
            "operating_system": "macOS",
            "color": "Midnight",
        },
    ),
    _product(
        "Dell XPS 14 (9440)",
        "DEL-XPS14-9440",
        "Dell",
        "Ultrabooks",
        224999,
        181000,
        6,
        "Intel Core Ultra 7, 16GB RAM and a 1TB SSD in a machined aluminium body.",
        "The XPS 14 blends a 3.2K OLED display with Intel Core Ultra efficiency and a premium CNC aluminium chassis. "
        "A superb choice for creative professionals who travel often.",
        [
            "Intel Core Ultra 7 155H processor",
            "14.5-inch 3.2K OLED touch display",
            "NVIDIA GeForce RTX 4050 graphics",
            "Quad speakers with Dolby Atmos",
        ],
        [
            ("Processor", "Intel Core Ultra 7 155H", ""),
            ("RAM", "16", "GB LPDDR5x"),
            ("Storage", "1", "TB NVMe SSD"),
            ("Graphics", "NVIDIA GeForce RTX 4050", ""),
            ("Display", "14.5", "inches"),
            ("Operating system", "Windows 11 Home", ""),
        ],
        "photo-1593642632823-8f785ba67e45",
        featured=True,
        facets={
            "processor": "Intel Core Ultra 7",
            "ram": "16GB",
            "storage": "1TB",
            "gpu": "RTX 4050",
            "display_size": "14.5",
            "operating_system": "Windows 11",
            "color": "Platinum",
        },
    ),
    _product(
        "ASUS ROG Zephyrus G14 (2024)",
        "ASU-ROG-G14-2024",
        "Asus",
        "Gaming Laptops",
        259999,
        214000,
        4,
        "Ryzen 9, RTX 4060 and a 165Hz OLED panel in a 1.5kg gaming laptop.",
        "The Zephyrus G14 is the gaming laptop we recommend when you also need to carry it to class or the office. "
        "Its OLED display is superb and the RTX 4060 handles modern titles at high settings.",
        [
            "AMD Ryzen 9 8945HS processor",
            "NVIDIA GeForce RTX 4060 8GB",
            "14-inch 3K 165Hz OLED display",
            "1.5kg magnesium alloy chassis",
        ],
        [
            ("Processor", "AMD Ryzen 9 8945HS", ""),
            ("RAM", "16", "GB LPDDR5x"),
            ("Storage", "1", "TB NVMe SSD"),
            ("Graphics", "NVIDIA GeForce RTX 4060", ""),
            ("Display", "14", "inches"),
            ("Operating system", "Windows 11 Home", ""),
        ],
        "photo-1588872657578-7efd1f1555ed",
        discount=244999,
        featured=True,
        facets={
            "processor": "Ryzen 9",
            "ram": "16GB",
            "storage": "1TB",
            "gpu": "RTX 4060",
            "display_size": "14",
            "operating_system": "Windows 11",
            "color": "Eclipse Gray",
        },
    ),
    _product(
        "Lenovo ThinkPad X1 Carbon Gen 12",
        "LEN-X1C-G12",
        "Lenovo",
        "Ultrabooks",
        209999,
        173000,
        3,
        "Business-class durability, 32GB RAM and an excellent keyboard.",
        "The X1 Carbon remains the benchmark for business ultrabooks. It is lightweight, repairable and built to survive "
        "the daily commute, with a keyboard that is still the best in the business.",
        [
            "Intel Core Ultra 7 155U processor",
            "32GB LPDDR5x memory",
            "14-inch 2.8K OLED display",
            "Mil-spec tested chassis",
        ],
        [
            ("Processor", "Intel Core Ultra 7 155U", ""),
            ("RAM", "32", "GB LPDDR5x"),
            ("Storage", "1", "TB NVMe SSD"),
            ("Graphics", "Intel Arc integrated", ""),
            ("Display", "14", "inches"),
            ("Operating system", "Windows 11 Pro", ""),
        ],
        "photo-1496181133206-80ce9b88a853",
        facets={
            "processor": "Intel Core Ultra 7",
            "ram": "32GB",
            "storage": "1TB",
            "gpu": "Intel Arc",
            "display_size": "14",
            "operating_system": "Windows 11",
            "color": "Deep Black",
        },
    ),
    _product(
        "HP Spectre x360 14",
        "HP-SPECTRE-14",
        "HP",
        "Ultrabooks",
        194999,
        160000,
        0,
        "A 2-in-1 convertible with an OLED touchscreen and included stylus.",
        "The Spectre x360 is a premium convertible for people who sketch, present and write on the go. "
        "The bundled stylus and 360-degree hinge make it unusually versatile.",
        [
            "Intel Core Ultra 7 155H processor",
            "14-inch 2.8K OLED touchscreen",
            "360-degree convertible hinge",
            "Includes rechargeable stylus",
        ],
        [
            ("Processor", "Intel Core Ultra 7 155H", ""),
            ("RAM", "16", "GB LPDDR5x"),
            ("Storage", "1", "TB NVMe SSD"),
            ("Graphics", "Intel Arc integrated", ""),
            ("Display", "14", "inches"),
            ("Operating system", "Windows 11 Home", ""),
        ],
        "photo-1541807084-5c52b6b3adef",
        discount=184999,
        facets={
            "processor": "Intel Core Ultra 7",
            "ram": "16GB",
            "storage": "1TB",
            "gpu": "Intel Arc",
            "display_size": "14",
            "operating_system": "Windows 11",
            "color": "Nightfall Black",
        },
    ),
    _product(
        "iPhone 15 Pro",
        "APL-IP15PRO",
        "Apple",
        "Flagship Phones",
        164999,
        136000,
        10,
        "Titanium build, A17 Pro and a versatile 48MP camera system.",
        "The iPhone 15 Pro brings a lighter titanium frame, USB-C and the A17 Pro chip. "
        "It remains one of the best cameras you can carry in a pocket.",
        [
            "A17 Pro chip with 6-core GPU",
            "48MP main camera with 3x telephoto",
            "6.1-inch Super Retina XDR display",
            "Titanium frame with USB-C",
        ],
        [
            ("Processor", "Apple A17 Pro", ""),
            ("RAM", "8", "GB"),
            ("Storage", "256", "GB"),
            ("Display", "6.1", "inches"),
            ("Battery", "3274", "mAh"),
            ("Rear camera", "48", "MP"),
        ],
        "photo-1592750475338-74b7b21085ab",
        featured=True,
        facets={
            "processor": "Apple A17 Pro",
            "ram": "8GB",
            "storage": "256GB",
            "display_size": "6.1",
            "operating_system": "iOS 17",
            "color": "Natural Titanium",
        },
    ),
    _product(
        "Samsung Galaxy S24 Ultra",
        "SAM-S24U",
        "Samsung",
        "Flagship Phones",
        184999,
        150000,
        8,
        "Built-in S Pen, 200MP camera and a bright 6.8-inch QHD+ display.",
        "The Galaxy S24 Ultra is the most complete Android phone for productivity. The S Pen, "
        "seven years of updates and exceptional zoom camera make it a long-term investment.",
        [
            "Snapdragon 8 Gen 3 for Galaxy",
            "200MP main camera with 5x optical zoom",
            "6.8-inch QHD+ 120Hz AMOLED display",
            "Built-in S Pen and Galaxy AI tools",
        ],
        [
            ("Processor", "Snapdragon 8 Gen 3", ""),
            ("RAM", "12", "GB"),
            ("Storage", "512", "GB"),
            ("Display", "6.8", "inches"),
            ("Battery", "5000", "mAh"),
            ("Rear camera", "200", "MP"),
        ],
        "photo-1610945265064-0e34e5519bbf",
        discount=174999,
        featured=True,
        facets={
            "processor": "Snapdragon 8 Gen 3",
            "ram": "12GB",
            "storage": "512GB",
            "display_size": "6.8",
            "operating_system": "Android 14",
            "color": "Titanium Gray",
        },
    ),
    _product(
        "Google Pixel 8 Pro",
        "GOO-PIX8PRO",
        "Google",
        "Flagship Phones",
        139999,
        114000,
        5,
        "The most helpful camera phone, with seven years of Android updates.",
        "Pixel 8 Pro focuses on computational photography and genuinely useful AI features. "
        "If you want the best point-and-shoot camera experience on Android, this is it.",
        [
            "Google Tensor G3 processor",
            "50MP main camera with 5x telephoto",
            "6.7-inch Super Actua display",
            "Seven years of OS and security updates",
        ],
        [
            ("Processor", "Google Tensor G3", ""),
            ("RAM", "12", "GB"),
            ("Storage", "256", "GB"),
            ("Display", "6.7", "inches"),
            ("Battery", "5050", "mAh"),
            ("Rear camera", "50", "MP"),
        ],
        "photo-1598327105666-5b89351aff97",
        facets={
            "processor": "Google Tensor G3",
            "ram": "12GB",
            "storage": "256GB",
            "display_size": "6.7",
            "operating_system": "Android 14",
            "color": "Obsidian",
        },
    ),
    _product(
        "Xiaomi 14",
        "XIA-14",
        "Xiaomi",
        "Flagship Phones",
        99999,
        81000,
        15,
        "Leica optics and Snapdragon 8 Gen 3 at a competitive price.",
        "The Xiaomi 14 is a compact flagship with Leica-tuned cameras and fast 90W charging. "
        "It is a strong alternative to pricier flagships without giving up performance.",
        [
            "Snapdragon 8 Gen 3 processor",
            "Leica triple camera system",
            "6.36-inch 120Hz AMOLED display",
            "90W wired HyperCharge",
        ],
        [
            ("Processor", "Snapdragon 8 Gen 3", ""),
            ("RAM", "12", "GB"),
            ("Storage", "256", "GB"),
            ("Display", "6.36", "inches"),
            ("Battery", "4610", "mAh"),
            ("Rear camera", "50", "MP"),
        ],
        "photo-1511707171634-5f897ff02aa9",
        facets={
            "processor": "Snapdragon 8 Gen 3",
            "ram": "12GB",
            "storage": "256GB",
            "display_size": "6.36",
            "operating_system": "Android 14",
            "color": "Jade Green",
        },
    ),
    _product(
        "Samsung Galaxy A55 5G",
        "SAM-A55",
        "Samsung",
        "Budget Phones",
        52999,
        43000,
        3,
        "A dependable mid-range phone with a bright AMOLED screen.",
        "The Galaxy A55 offers a premium feel, a large AMOLED display and long software support at a mid-range price. "
        "It is the safe choice for everyday use.",
        [
            "Exynos 1480 processor",
            "6.6-inch Super AMOLED 120Hz display",
            "50MP OIS main camera",
            "Four generations of OS updates",
        ],
        [
            ("Processor", "Exynos 1480", ""),
            ("RAM", "8", "GB"),
            ("Storage", "128", "GB"),
            ("Display", "6.6", "inches"),
            ("Battery", "5000", "mAh"),
            ("Rear camera", "50", "MP"),
        ],
        "photo-1510557880182-3d4d3cba35a5",
        discount=48999,
        threshold=4,
        facets={
            "processor": "Exynos 1480",
            "ram": "8GB",
            "storage": "128GB",
            "display_size": "6.6",
            "operating_system": "Android 14",
            "color": "Awesome Navy",
        },
    ),
    _product(
        "Sony WH-1000XM5",
        "SON-WH1000XM5",
        "Sony",
        "Headphones",
        46999,
        38000,
        9,
        "Industry-leading noise cancellation with 30-hour battery life.",
        "The WH-1000XM5 is still the reference for travel noise cancellation. "
        "Comfortable for long flights, with excellent call quality and multipoint Bluetooth.",
        [
            "Eight microphones with two processors",
            "Up to 30 hours of battery life",
            "Multipoint Bluetooth connection",
            "Foldable carry case included",
        ],
        [
            ("Driver size", "30", "mm"),
            ("Battery life", "30", "hours"),
            ("Connectivity", "Bluetooth 5.2, USB-C, 3.5mm", ""),
            ("Noise cancellation", "Adaptive ANC", ""),
        ],
        "photo-1505740420928-5e560c06d30e",
        featured=True,
        facets={"color": "Black", "operating_system": ""},
    ),
    _product(
        "Apple AirPods Pro (2nd generation)",
        "APL-AIRPODS-PRO2",
        "Apple",
        "Earbuds & Speakers",
        32999,
        26500,
        14,
        "USB-C charging, adaptive audio and excellent transparency mode.",
        "AirPods Pro remain the most seamless earbuds for iPhone users. "
        "Adaptive audio adjusts noise cancellation automatically through the day.",
        [
            "H2 chip with adaptive audio",
            "Up to 6 hours listening, 30 hours with case",
            "USB-C MagSafe charging case",
            "IP54 dust and water resistance",
        ],
        [
            ("Driver size", "11", "mm"),
            ("Battery life", "6", "hours"),
            ("Connectivity", "Bluetooth 5.3, USB-C", ""),
            ("Noise cancellation", "Active ANC", ""),
        ],
        "photo-1606220945770-b5b6c2c55bf1",
        facets={"color": "White", "operating_system": ""},
    ),
    _product(
        "JBL Charge 5",
        "JBL-CHARGE5",
        "JBL",
        "Earbuds & Speakers",
        21999,
        17300,
        2,
        "Portable Bluetooth speaker with 20 hours of playback and a power bank.",
        "The Charge 5 is a rugged outdoor speaker that can also top up your phone. "
        "Bass is punchy and the IP67 rating means it can go anywhere.",
        [
            "20 hours of playtime",
            "IP67 dust and water rating",
            "Built-in power bank",
            "PartyBoost for multiple speakers",
        ],
        [
            ("Driver size", "52", "mm"),
            ("Battery life", "20", "hours"),
            ("Connectivity", "Bluetooth 5.1, USB-C", ""),
            ("Noise cancellation", "No", ""),
        ],
        "photo-1608043152269-423dbba4e7e1",
        discount=19999,
        threshold=4,
        facets={"color": "Blue", "operating_system": ""},
    ),
    _product(
        "Bose QuietComfort Ultra Headphones",
        "BOS-QC-ULTRA",
        "Bose",
        "Headphones",
        54999,
        44500,
        6,
        "Immersive spatial audio with Bose's best noise cancellation.",
        "The QuietComfort Ultra adds immersive spatial audio to Bose's class-leading cancellation. "
        "A premium option for frequent flyers who value comfort above all.",
        [
            "Bose Immersive Audio",
            "Up to 24 hours of battery life",
            "CustomTune calibration",
            "Premium cushioned ear cups",
        ],
        [
            ("Driver size", "35", "mm"),
            ("Battery life", "24", "hours"),
            ("Connectivity", "Bluetooth 5.3, 3.5mm", ""),
            ("Noise cancellation", "QuietComfort ANC", ""),
        ],
        "photo-1546435770-a3e426bf472b",
        facets={"color": "Black", "operating_system": ""},
    ),
    _product(
        "PlayStation 5 Slim",
        "SON-PS5-SLIM",
        "Sony",
        "Consoles",
        89999,
        75000,
        5,
        "1TB storage, 4K gaming and the DualSense wireless controller.",
        "The PS5 Slim is the current-generation console to beat for exclusives. "
        "The DualSense haptics remain genuinely transformative in supported titles.",
        [
            "1TB custom NVMe SSD",
            "4K gaming up to 120fps",
            "DualSense wireless controller included",
            "Disc drive included",
        ],
        [
            ("Platform", "PlayStation 5", ""),
            ("Storage", "1024", "GB"),
            ("Resolution", "4K", ""),
            ("Controller", "DualSense", ""),
        ],
        "photo-1606144042614-b2417e99c4e3",
        featured=True,
        facets={"storage": "1TB", "color": "White"},
    ),
    _product(
        "Xbox Series X",
        "MSC-XBOX-SX",
        "Microsoft",
        "Consoles",
        84999,
        70500,
        0,
        "12 teraflops of power, 1TB SSD and Quick Resume.",
        "The Series X is the most powerful Xbox ever, with fast load times and Quick Resume. "
        "Game Pass makes it an excellent value if you play a lot of different titles.",
        [
            "12 teraflops of GPU performance",
            "1TB custom NVMe SSD",
            "4K gaming up to 120fps",
            "Quick Resume across multiple games",
        ],
        [
            ("Platform", "Xbox Series X", ""),
            ("Storage", "1024", "GB"),
            ("Resolution", "4K", ""),
            ("Controller", "Xbox Wireless Controller", ""),
        ],
        "photo-1621259182978-fbf93132d53d",
        facets={"storage": "1TB", "color": "Black"},
    ),
    _product(
        "Logitech G502 X Lightspeed",
        "LOG-G502X",
        "Logitech",
        "Gaming Gear",
        12999,
        10200,
        20,
        "Wireless gaming mouse with Hero 25K sensor and 140-hour battery.",
        "The G502 X keeps the iconic shape and adds a lighter build with optical switches. "
        "A dependable daily driver for both work and competitive play.",
        [
            "Hero 25K optical sensor",
            "Up to 140 hours of battery life",
            "Lightforce optical switches",
            "13 programmable controls",
        ],
        [
            ("Type", "Wireless gaming mouse", ""),
            ("Connectivity", "Lightspeed wireless, USB-C", ""),
            ("Battery life", "140", "hours"),
            ("Weight", "102", "g"),
        ],
        "photo-1527814050087-3793815479db",
        facets={"color": "Black"},
    ),
    _product(
        "Razer BlackWidow V4 Pro",
        "RAZ-BW-V4",
        "Razer",
        "Gaming Gear",
        17999,
        14200,
        4,
        "Mechanical keyboard with command dial and per-key Chroma lighting.",
        "The BlackWidow V4 Pro is a full-size mechanical keyboard with a command dial, macro keys and "
        "Razer's tactile green switches. It is built for people who want everything within reach.",
        [
            "Razer green mechanical switches",
            "Programmable command dial",
            "Per-key Chroma RGB lighting",
            "Magnetic plush wrist rest",
        ],
        [
            ("Type", "Mechanical keyboard", ""),
            ("Connectivity", "USB-C wired", ""),
            ("Battery life", "0", "hours"),
            ("Weight", "1510", "g"),
        ],
        "photo-1595225476474-87563907a212",
        discount=16499,
        threshold=4,
        facets={"color": "Black"},
    ),
    _product(
        "LG UltraGear 27GP850",
        "LG-27GP850",
        "LG",
        "Monitors",
        64999,
        53000,
        7,
        "27-inch QHD Nano IPS monitor with 165Hz refresh and 1ms response.",
        "The 27GP850 is a well-rounded gaming monitor with excellent motion handling and accurate colours. "
        "It doubles as a comfortable display for design work.",
        [
            "27-inch QHD Nano IPS panel",
            "165Hz refresh rate, 1ms GtG",
            "NVIDIA G-Sync compatible",
            "HDR10 with 98% DCI-P3",
        ],
        [
            ("Panel type", "Nano IPS", ""),
            ("Resolution", "2560 x 1440", ""),
            ("Refresh rate", "165", "Hz"),
            ("Screen size", "27", "inches"),
        ],
        "photo-1541140532154-b024d705b90a",
        facets={"color": "Black"},
    ),
    _product(
        "Dell UltraSharp U2723QE",
        "DEL-U2723QE",
        "Dell",
        "Monitors",
        89999,
        74500,
        3,
        "27-inch 4K IPS Black monitor with USB-C hub and 90W charging.",
        "A professional 4K monitor with an integrated USB-C hub that can power a laptop. "
        "IPS Black delivers deeper blacks and better contrast than typical IPS panels.",
        [
            "27-inch 4K IPS Black panel",
            "USB-C hub with 90W power delivery",
            "98% DCI-P3 colour coverage",
            "Built-in KVM switch",
        ],
        [
            ("Panel type", "IPS Black", ""),
            ("Resolution", "3840 x 2160", ""),
            ("Refresh rate", "60", "Hz"),
            ("Screen size", "27", "inches"),
        ],
        "photo-1527443224154-c4a3942d3acf",
        facets={"color": "Silver"},
    ),
    _product(
        "NVIDIA GeForce RTX 4070 Super",
        "NVIDIA-RTX4070S",
        "NVIDIA",
        "Graphics Cards",
        94999,
        79000,
        6,
        "12GB GDDR6X, DLSS 3 and excellent 1440p performance.",
        "The RTX 4070 Super is the sweet spot for 1440p gaming with ray tracing enabled. "
        "DLSS 3 frame generation stretches demanding titles further.",
        [
            "12GB GDDR6X memory",
            "DLSS 3 with frame generation",
            "7168 CUDA cores",
            "PCIe 4.0 interface",
        ],
        [
            ("Type", "Desktop graphics card", ""),
            ("Capacity", "12", "GB GDDR6X"),
            ("Interface", "PCIe 4.0 x16", ""),
            ("Memory type", "GDDR6X", ""),
        ],
        "photo-1587202372775-e229f172b9d7",
        facets={"gpu": "RTX 4070 Super", "storage": "12GB"},
    ),
    _product(
        "Samsung 990 PRO 2TB NVMe SSD",
        "SAM-990PRO-2TB",
        "Samsung",
        "Storage & Memory",
        24999,
        19800,
        11,
        "PCIe 4.0 NVMe drive with up to 7450 MB/s sequential reads.",
        "The 990 PRO is one of the fastest PCIe 4.0 drives available and a straightforward upgrade "
        "for a laptop or desktop that feels slow.",
        [
            "Up to 7450 MB/s sequential read",
            "2TB capacity",
            "PCIe 4.0 x4 NVMe 2.0",
            "Five-year limited warranty",
        ],
        [
            ("Type", "NVMe SSD", ""),
            ("Capacity", "2", "TB"),
            ("Interface", "PCIe 4.0 x4", ""),
            ("Memory type", "V-NAND TLC", ""),
        ],
        "photo-1597872200969-2b65d56bd16b",
        facets={"storage": "2TB"},
    ),
    _product(
        "Apple Watch Series 9",
        "APL-WATCH-S9",
        "Apple",
        "Wearables",
        64999,
        53500,
        8,
        "S9 chip, double tap gesture and a bright always-on display.",
        "The Series 9 is the most polished smartwatch for iPhone users. "
        "Health tracking, crash detection and the double tap gesture make it genuinely useful.",
        [
            "S9 SiP with double tap gesture",
            "45mm always-on Retina display",
            "ECG and blood oxygen sensors",
            "50m water resistance",
        ],
        [
            ("Display", "45mm OLED", ""),
            ("Battery life", "18", "hours"),
            ("Water resistance", "50m", ""),
            ("Connectivity", "Bluetooth, Wi-Fi, LTE optional", ""),
        ],
        "photo-1546868871-7041f2a55e12",
        featured=True,
        facets={"color": "Midnight"},
    ),
    _product(
        "Samsung Galaxy Watch 6",
        "SAM-GW6",
        "Samsung",
        "Wearables",
        39999,
        32500,
        5,
        "Slim bezel, sleep coaching and comprehensive health tracking.",
        "The Galaxy Watch 6 is the best smartwatch for Android users, with detailed sleep tracking "
        "and a bright AMOLED display in a comfortable case.",
        [
            "1.5-inch Super AMOLED display",
            "Advanced sleep coaching",
            "Body composition analysis",
            "5ATM and IP68 water resistance",
        ],
        [
            ("Display", "1.5-inch AMOLED", ""),
            ("Battery life", "40", "hours"),
            ("Water resistance", "5ATM + IP68", ""),
            ("Connectivity", "Bluetooth 5.3, Wi-Fi", ""),
        ],
        "photo-1523275335684-37898b6baf30",
        discount=36999,
        facets={"color": "Graphite"},
    ),
    _product(
        "TP-Link Deco X50 (3-pack)",
        "TPL-DECO-X50",
        "TP-Link",
        "Networking",
        27999,
        22000,
        10,
        "Wi-Fi 6 mesh system covering up to 6500 sq ft with three units.",
        "The Deco X50 is an easy mesh upgrade for a multi-storey home. "
        "Three units provide strong coverage and seamless roaming between rooms.",
        [
            "Wi-Fi 6 AX3000 mesh system",
            "Coverage up to 6500 sq ft",
            "Supports up to 150 devices",
            "Easy app-based setup",
        ],
        [
            ("Wi-Fi standard", "Wi-Fi 6 (802.11ax)", ""),
            ("Coverage", "6500", "sq ft"),
            ("Ports", "3x Gigabit per unit", ""),
            ("Speed", "3000", "Mbps"),
        ],
        "photo-1558494949-ef010cbdcc31",
        facets={"color": "White"},
    ),
    _product(
        "Anker 737 Power Bank (24,000mAh)",
        "ANK-737",
        "Anker",
        "Power & Charging",
        14999,
        11800,
        18,
        "140W output, smart display and enough capacity for a laptop.",
        "The Anker 737 can charge a 14-inch laptop, a phone and earbuds at the same time. "
        "The digital display shows exact remaining capacity and output wattage.",
        [
            "24,000mAh capacity",
            "140W maximum output",
            "Digital power display",
            "Two USB-C and one USB-A port",
        ],
        [
            ("Capacity", "24000", "mAh"),
            ("Output", "140", "W"),
            ("Connector", "USB-C, USB-A", ""),
            ("Compatibility", "Laptops, phones, tablets", ""),
        ],
        "photo-1609091839311-d5365f9ff1c5",
        facets={"color": "Black"},
    ),
]

# ---------------------------------------------------------------------------
# People, marketing and sales demo data
# ---------------------------------------------------------------------------
DEMO_USERS = [
    ("admin@voltiq.com", ADMIN_PASSWORD, "Aarati", "Shrestha", User.Role.ADMIN, True, True),
    ("staff@voltiq.com", STAFF_PASSWORD, "Rohan", "Basnet", User.Role.STAFF, True, False),
    ("aarav.sharma@example.com", DEMO_PASSWORD, "Aarav", "Sharma", User.Role.CUSTOMER, False, False),
    ("priya.thapa@example.com", DEMO_PASSWORD, "Priya", "Thapa", User.Role.CUSTOMER, False, False),
    ("bibek.gurung@example.com", DEMO_PASSWORD, "Bibek", "Gurung", User.Role.CUSTOMER, False, False),
    ("sita.rai@example.com", DEMO_PASSWORD, "Sita", "Rai", User.Role.CUSTOMER, False, False),
    ("nischal.karki@example.com", DEMO_PASSWORD, "Nischal", "Karki", User.Role.CUSTOMER, False, False),
    ("anisha.shrestha@example.com", DEMO_PASSWORD, "Anisha", "Shrestha", User.Role.CUSTOMER, False, False),
]

ADDRESSES = {
    "aarav.sharma@example.com": ("Home", "Aarav Sharma", "+977 980-111-2233", "House 12, Jhamsikhel", "Lalitpur", "Lalitpur", "bagmati", "44700"),
    "priya.thapa@example.com": ("Home", "Priya Thapa", "+977 981-222-3344", "Apartment 4B, Baluwatar", "Kathmandu", "Kathmandu", "bagmati", "44600"),
    "bibek.gurung@example.com": ("Home", "Bibek Gurung", "+977 982-333-4455", "Lakeside Road 6", "Pokhara", "Kaski", "gandaki", "33700"),
    "sita.rai@example.com": ("Home", "Sita Rai", "+977 984-444-5566", "Dharan Road 9", "Biratnagar", "Morang", "koshi", "56600"),
    "nischal.karki@example.com": ("Home", "Nischal Karki", "+977 985-555-6677", "Baneshwor Height", "Kathmandu", "Kathmandu", "bagmati", "44600"),
    "anisha.shrestha@example.com": ("Home", "Anisha Shrestha", "+977 986-666-7788", "Nayabazar", "Kathmandu", "Kathmandu", "bagmati", "44600"),
}

SHIPPING_METHODS = [
    ("Standard Delivery", "standard", "Delivery across Nepal within 2–4 working days.", 250, 10000, 2, 4, 1),
    ("Kathmandu Express", "express", "Same-day dispatch and 1–2 day delivery inside the valley.", 450, 15000, 1, 2, 2),
    ("Store Pickup", "pickup", "Collect free from our Durbar Marg showroom.", 0, None, 1, 1, 3),
]

COUPONS = [
    ("WELCOME10", "10% off your first order (capped at Rs. 1,500).", "percentage", 10, 5000, 1500, 500, 1),
    ("VOLTIQ500", "Rs. 500 off orders over Rs. 10,000.", "fixed", 500, 10000, None, 300, 2),
    ("SAVE15", "15% off orders over Rs. 20,000 (capped at Rs. 5,000).", "percentage", 15, 20000, 5000, 100, 1),
]

ORDERS = [
    ("aarav.sharma@example.com", [("APL-MBA13-M3", 1), ("APL-AIRPODS-PRO2", 1)], "express", Order.Status.DELIVERED, Order.PaymentMethod.ESEWA, True, 28, "WELCOME10"),
    ("priya.thapa@example.com", [("SAM-S24U", 1)], "standard", Order.Status.DELIVERED, Order.PaymentMethod.KHALTI, True, 24, None),
    ("bibek.gurung@example.com", [("SON-WH1000XM5", 1)], "standard", Order.Status.DELIVERED, Order.PaymentMethod.COD, True, 20, None),
    ("sita.rai@example.com", [("LG-27GP850", 1), ("LOG-G502X", 1)], "standard", Order.Status.SHIPPED, Order.PaymentMethod.ESEWA, True, 14, None),
    ("nischal.karki@example.com", [("NVIDIA-RTX4070S", 1)], "express", Order.Status.PROCESSING, Order.PaymentMethod.KHALTI, True, 10, "SAVE15"),
    ("anisha.shrestha@example.com", [("DEL-U2723QE", 1)], "standard", Order.Status.CONFIRMED, Order.PaymentMethod.BANK, True, 7, None),
    ("aarav.sharma@example.com", [("ANK-737", 1)], "standard", Order.Status.PENDING, Order.PaymentMethod.COD, False, 3, None),
    ("priya.thapa@example.com", [("XIA-14", 1)], "express", Order.Status.DELIVERED, Order.PaymentMethod.ESEWA, True, 32, None),
    ("bibek.gurung@example.com", [("SON-PS5-SLIM", 1)], "standard", Order.Status.OUT_FOR_DELIVERY, Order.PaymentMethod.COD, True, 5, None),
    ("sita.rai@example.com", [("SAM-A55", 1)], "standard", Order.Status.CANCELLED, Order.PaymentMethod.COD, False, 18, None),
    ("nischal.karki@example.com", [("TPL-DECO-X50", 1), ("SAM-990PRO-2TB", 1)], "standard", Order.Status.PENDING, Order.PaymentMethod.BANK, False, 1, None),
    ("anisha.shrestha@example.com", [("APL-WATCH-S9", 1)], "express", Order.Status.DELIVERED, Order.PaymentMethod.KHALTI, True, 40, None),
    ("aarav.sharma@example.com", [("BOS-QC-ULTRA", 1)], "standard", Order.Status.DELIVERED, Order.PaymentMethod.ESEWA, True, 45, None),
    ("priya.thapa@example.com", [("RAZ-BW-V4", 1)], "standard", Order.Status.PENDING, Order.PaymentMethod.ESEWA, False, 0, None),
]

EXTRA_REVIEWS = [
    ("APL-IP15PRO", "priya.thapa@example.com", 5, "Camera and battery are superb", "Upgraded from an older iPhone and the difference is night and day. The titanium frame feels much lighter in hand."),
    ("SAM-S24U", "nischal.karki@example.com", 5, "The S Pen is genuinely useful", "I use it for notes in meetings every day. The screen is bright enough to use outdoors in Kathmandu."),
    ("SON-WH1000XM5", "anisha.shrestha@example.com", 4, "Excellent on flights", "Noise cancellation is outstanding. The case is a little bulky but worth it for travel."),
    ("SON-PS5-SLIM", "aarav.sharma@example.com", 5, "Fantastic console", "The load times are basically gone. DualSense haptics are the highlight."),
    ("LG-27GP850", "sita.rai@example.com", 4, "Great value gaming monitor", "Colours are accurate out of the box and 165Hz feels smooth. Stand could be better."),
    ("APL-WATCH-S9", "bibek.gurung@example.com", 5, "Best smartwatch for iPhone", "Sleep tracking and the double tap gesture are the features I use most."),
    ("HP-SPECTRE-14", "anisha.shrestha@example.com", 3, "Beautiful but runs warm", "The screen is stunning and the stylus is great, but it gets warm during video calls."),
    ("SAM-990PRO-2TB", "nischal.karki@example.com", 5, "Huge speed upgrade", "Cloned my old drive and everything feels instant now. Worth it."),
    ("ANK-737", "priya.thapa@example.com", 5, "Charges my laptop", "Took it on a trek and it charged my phone three times plus my laptop once."),
    ("TPL-DECO-X50", "bibek.gurung@example.com", 4, "Fixed our dead spots", "Setup took ten minutes and the whole house is covered now."),
]

NEWSLETTER = [
    ("aarav.sharma@example.com", "Aarav Sharma", "footer", True),
    ("priya.thapa@example.com", "Priya Thapa", "checkout", True),
    ("bibek.gurung@example.com", "Bibek Gurung", "footer", True),
    ("sita.rai@example.com", "Sita Rai", "popup", True),
    ("nischal.karki@example.com", "Nischal Karki", "footer", True),
    ("anisha.shrestha@example.com", "Anisha Shrestha", "checkout", True),
    ("sujan.maharjan@example.com", "Sujan Maharjan", "footer", True),
    ("pooja.adhikari@example.com", "Pooja Adhikari", "footer", False),
]

CONTACT_MESSAGES = [
    ("Ramesh Koirala", "ramesh.koirala@example.com", "+977 980-777-8899", "Warranty question for ThinkPad", "Hello, I bought a ThinkPad X1 Carbon last month. Does the international warranty cover a keyboard replacement in Kathmandu?", ContactMessage.Status.NEW),
    ("Sunita Bhandari", "sunita.bhandari@example.com", "+977 981-888-9900", "Bulk order for an office", "We need 15 monitors and 15 docking stations for a new office in Lalitpur. Can you send a quotation?", ContactMessage.Status.IN_PROGRESS),
    ("Kiran Lama", "kiran.lama@example.com", "", "Delivery to Pokhara", "Do you deliver the PS5 to Pokhara? What is the expected delivery time and is cash on delivery available?", ContactMessage.Status.RESOLVED),
    ("Maya Tamang", "maya.tamang@example.com", "+977 984-999-0011", "eSewa payment failed", "My eSewa payment showed failed but the amount was deducted. Order VQ-240101-ABC123. Please help.", ContactMessage.Status.NEW),
]

REVIEW_TITLES = [
    "Excellent purchase",
    "Exactly as described",
    "Great value for the price",
    "Would buy again",
    "Impressive performance",
    "Solid everyday device",
]
REVIEW_BODIES = [
    "Delivery was quick and the product arrived well packaged. It has performed exactly as expected over the last few weeks.",
    "The build quality is excellent and setup was straightforward. I would happily recommend it to a friend.",
    "Good value considering the local warranty and support. The store answered my questions before I ordered.",
    "I have been using it daily and it has handled everything I need without any issues.",
    "The specs are accurate and the product feels premium. Packaging and delivery were both excellent.",
    "Works well for my needs. Battery life and performance are both better than I expected.",
]


class Command(BaseCommand):
    help = "Populate the Voltiq database with a realistic demo catalogue and store data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-images",
            action="store_true",
            help="Do not download product images (uses no images at all).",
        )

    def handle(self, *args, **options):
        skip_images = options["skip_images"]
        now = timezone.now()
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding Voltiq demo store"))

        with transaction.atomic():
            categories = self._seed_categories()
            brands = self._seed_brands()
            self._seed_spec_fields(categories)
            products = self._seed_products(categories, brands)
            self._seed_stock_history(products)
            shipping = self._seed_shipping()
            coupons = self._seed_coupons(now)
            users = self._seed_users(now)
            self._seed_addresses(users)
            orders = self._seed_orders(users, products, shipping, coupons, now)
            self._seed_reviews(orders, products, users)
            self._seed_wishlist(products, users)
            self._seed_newsletter()
            self._seed_messages()
            self._seed_notifications(users, orders)
            self._seed_site_settings()

        if skip_images:
            self.stdout.write(self.style.WARNING("Skipped product images (--skip-images)."))
        else:
            self._seed_images(products)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo store ready."))
        self.stdout.write("  Catalogue: %d categories · %d brands · %d products" % (
            len(categories), len(brands), len(products)
        ))
        self.stdout.write("  Sales:     %d orders · %d reviews · %d coupons" % (
            len(orders), Review.objects.count(), len(coupons)
        ))
        self.stdout.write("")
        self.stdout.write("  Storefront: http://127.0.0.1:8000/")
        self.stdout.write("  Dashboard:  http://127.0.0.1:8000/dashboard/")
        self.stdout.write("  Admin:      http://127.0.0.1:8000/django-admin/")
        self.stdout.write("")
        self.stdout.write("  Demo accounts:")
        self.stdout.write(f"    Administrator  admin@voltiq.com / {ADMIN_PASSWORD}")
        self.stdout.write(f"    Staff          staff@voltiq.com / {STAFF_PASSWORD}")
        self.stdout.write(f"    Customer       aarav.sharma@example.com / {DEMO_PASSWORD}")

    # -- catalogue ---------------------------------------------------------
    def _seed_categories(self):
        created = {}
        for name, icon, parent_name, description, sort_order in CATEGORIES:
            parent = created.get(parent_name) if parent_name else None
            category, _ = Category.objects.update_or_create(
                name=name,
                defaults={
                    "parent": parent,
                    "icon": icon,
                    "description": description,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_featured": parent is None,
                },
            )
            created[name] = category
        self._cache_clear()
        return created

    def _seed_brands(self):
        created = {}
        for name, website in BRANDS:
            description = f"Official {name} products with local warranty and support."
            brand, _ = Brand.objects.update_or_create(
                name=name,
                defaults={"website": website, "description": description, "is_active": True, "is_featured": True},
            )
            created[name] = brand
        return created

    def _seed_spec_fields(self, categories):
        for name, category in categories.items():
            root = category.parent.name if category.parent else category.name
            fields = CATEGORY_FIELD_OVERRIDES.get(name) or FIELD_SETS.get(root, [])
            for index, (label, unit, input_type, filterable) in enumerate(fields):
                SpecificationField.objects.get_or_create(
                    category=category,
                    key=slugify(label)[:80],
                    defaults={
                        "label": label,
                        "unit": unit,
                        "input_type": input_type,
                        "is_filterable": filterable,
                        "sort_order": index,
                    },
                )

    def _seed_products(self, categories, brands):
        products = {}
        for data in PRODUCTS:
            defaults = {
                "name": data["name"],
                "brand": brands[data["brand"]],
                "category": categories[data["category"]],
                "short_description": data["short"],
                "description": data["description"],
                "highlights": "\n".join(data["highlights"]),
                "price": Decimal(str(data["price"])),
                "discount_price": Decimal(str(data["discount"])) if data["discount"] else None,
                "cost_price": Decimal(str(data["cost"])),
                "stock_quantity": data["stock"],
                "low_stock_threshold": data["threshold"],
                "condition": data["condition"],
                "is_active": True,
                "is_featured": data["featured"],
                "free_shipping": data["price"] >= 10000,
                "meta_title": f"{data['name']} — Voltiq",
                "meta_description": data["short"][:300],
            }
            defaults.update(data["facets"])
            product, _ = Product.objects.update_or_create(sku=data["sku"], defaults=defaults)
            for index, (spec_name, value, unit) in enumerate(data["specs"]):
                ProductSpecification.objects.update_or_create(
                    product=product,
                    name=spec_name,
                    defaults={"value": value, "unit": unit, "sort_order": index},
                )
            products[data["sku"]] = product
        self._cache_clear()
        return products

    def _seed_stock_history(self, products):
        for product in products.values():
            StockHistory.objects.get_or_create(
                product=product,
                reason=StockHistory.Reason.SEED,
                reference="Demo catalogue",
                defaults={
                    "change": product.stock_quantity,
                    "previous_quantity": 0,
                    "new_quantity": product.stock_quantity,
                },
            )

    def _seed_images(self, products):
        self.stdout.write("Downloading product imagery…")
        for product in products.values():
            if product.images.exists():
                continue
            data = None
            source = next(
                (item for item in PRODUCTS if item["sku"] == product.sku),
                None,
            )
            if source:
                data = self._download(source["image"])
            if not data:
                data = self._placeholder(product.name)
            image = ProductImage(product=product, alt_text=product.name, is_primary=True)
            image.image.save(f"{product.sku.lower()}-1.jpg", ContentFile(data), save=False)
            image.save()
        with_images = sum(1 for item in products.values() if item.images.exists())
        self.stdout.write(self.style.SUCCESS(f"  {with_images} product(s) now have images."))

    @staticmethod
    def _download(url):
        try:
            response = requests.get(url, timeout=15, headers={"User-Agent": "VoltiqSeed/1.0"})
            response.raise_for_status()
            if len(response.content) < 2000:
                return None
            Image.open(io.BytesIO(response.content)).verify()
            return response.content
        except Exception:
            return None

    @staticmethod
    def _placeholder(name):
        width, height = 1200, 900
        top, bottom = (11, 18, 32), (37, 99, 235)
        image = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(image)
        for y in range(height):
            ratio = y / height
            draw.line(
                [(0, y), (width, y)],
                fill=(
                    int(top[0] + (bottom[0] - top[0]) * ratio),
                    int(top[1] + (bottom[1] - top[1]) * ratio),
                    int(top[2] + (bottom[2] - top[2]) * ratio),
                ),
            )
        try:
            font = ImageFont.truetype("arial.ttf", 62)
        except OSError:
            font = ImageFont.load_default()
        text = "\n".join(textwrap.wrap(name, 20)[:4])
        bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=16, align="center")
        x = (width - (bbox[2] - bbox[0])) / 2
        y = (height - (bbox[3] - bbox[1])) / 2
        draw.multiline_text((x, y), text, font=font, fill="white", spacing=16, align="center")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=88)
        return buffer.getvalue()

    # -- operations --------------------------------------------------------
    def _seed_shipping(self):
        methods = {}
        for name, code, description, charge, free_over, min_days, max_days, sort_order in SHIPPING_METHODS:
            method, _ = ShippingMethod.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": description,
                    "charge": Decimal(str(charge)),
                    "free_over": Decimal(str(free_over)) if free_over is not None else None,
                    "min_days": min_days,
                    "max_days": max_days,
                    "sort_order": sort_order,
                    "is_active": True,
                },
            )
            methods[code] = method
        return methods

    def _seed_coupons(self, now):
        coupons = {}
        for code, description, discount_type, value, minimum, maximum, usage_limit, per_user in COUPONS:
            coupon, _ = Coupon.objects.update_or_create(
                code=code,
                defaults={
                    "description": description,
                    "discount_type": discount_type,
                    "value": Decimal(str(value)),
                    "minimum_order_amount": Decimal(str(minimum)),
                    "maximum_discount": Decimal(str(maximum)) if maximum is not None else None,
                    "valid_from": now - timedelta(days=60),
                    "valid_to": now + timedelta(days=180),
                    "usage_limit": usage_limit,
                    "per_user_limit": per_user,
                    "is_active": True,
                },
            )
            coupons[code] = coupon
        return coupons

    def _seed_users(self, now):
        users = {}
        for email, password, first, last, role, is_admin, is_staff in DEMO_USERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": role,
                    "is_email_verified": True,
                    "email_verified_at": now,
                    "is_active": True,
                    "is_staff": is_staff or is_admin,
                    "is_superuser": is_admin,
                    "newsletter_opt_in": role == User.Role.CUSTOMER,
                    "date_joined": now - timedelta(days=60),
                },
            )
            if created:
                user.set_password(password)
                user.save()
            else:
                # Keep demo accounts usable and verified across re-runs.
                updates = []
                if not user.is_email_verified:
                    user.is_email_verified = True
                    user.email_verified_at = now
                    updates += ["is_email_verified", "email_verified_at"]
                if is_admin and (not user.is_superuser or not user.is_staff):
                    user.is_superuser = True
                    user.is_staff = True
                    user.role = User.Role.ADMIN
                    updates += ["is_superuser", "is_staff", "role"]
                if updates:
                    user.save(update_fields=updates)
            CustomerProfile.objects.get_or_create(user=user, defaults={"marketing_opt_in": role == User.Role.CUSTOMER})
            users[email] = user
        return users

    def _seed_addresses(self, users):
        for email, data in ADDRESSES.items():
            user = users.get(email)
            if not user:
                continue
            label, full_name, phone, street, city, district, province, postal = data
            Address.objects.update_or_create(
                user=user,
                label=label,
                defaults={
                    "full_name": full_name,
                    "phone": phone,
                    "street_address": street,
                    "city": city,
                    "district": district,
                    "province": province,
                    "postal_code": postal,
                    "country": "Nepal",
                    "address_type": Address.AddressType.BOTH,
                    "is_default": True,
                },
            )

    def _seed_orders(self, users, products, shipping, coupons, now):
        orders = []
        for index, (email, items, shipping_code, status, method, paid, days_ago, coupon_code) in enumerate(ORDERS, start=1):
            marker = f"Seed demo order {index:02d}"
            if Order.objects.filter(internal_notes=marker).exists():
                orders.append(Order.objects.filter(internal_notes=marker).first())
                continue

            customer = users[email]
            address = Address.objects.filter(user=customer).first()
            method_obj = shipping[shipping_code]
            coupon = coupons.get(coupon_code) if coupon_code else None
            created = now - timedelta(days=days_ago, hours=(index * 3) % 11, minutes=(index * 7) % 60)

            subtotal = Decimal("0")
            for sku, quantity in items:
                subtotal += products[sku].current_price * quantity
            subtotal = money(subtotal)
            discount = coupon.calculate_discount(subtotal) if coupon else Decimal("0")
            fee = method_obj.fee_for(subtotal)
            total = money(max(Decimal("0"), subtotal - discount + fee))

            if paid:
                payment_status = Order.PaymentStatus.PAID
            elif status == Order.Status.CANCELLED:
                payment_status = Order.PaymentStatus.FAILED
            else:
                payment_status = Order.PaymentStatus.PENDING

            order = Order.objects.create(
                user=customer,
                email=customer.email,
                phone=customer.phone or (address.phone if address else "+977 980-000-0000"),
                full_name=customer.get_full_name(),
                shipping_full_name=customer.get_full_name(),
                shipping_phone=address.phone if address else "+977 980-000-0000",
                shipping_street=address.street_address if address else "Durbar Marg",
                shipping_city=address.city if address else "Kathmandu",
                shipping_district=address.district if address else "Kathmandu",
                shipping_province=address.province if address else "bagmati",
                shipping_postal_code=address.postal_code if address else "44600",
                shipping_country="Nepal",
                shipping_method=method_obj,
                shipping_method_name=method_obj.name,
                shipping_fee=fee,
                subtotal=subtotal,
                coupon=coupon,
                coupon_code=coupon.code if coupon else "",
                discount_amount=discount,
                total=total,
                status=status,
                payment_status=payment_status,
                payment_method=method,
                internal_notes=marker,
                customer_notes="Please call before delivery." if index % 5 == 0 else "",
            )

            for sku, quantity in items:
                product = products[sku]
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    product_name=product.name,
                    sku=product.sku,
                    image_url=product.primary_image_url,
                    unit_price=product.current_price,
                    quantity=quantity,
                )
                Product.objects.filter(pk=product.pk).update(sales_count=F("sales_count") + quantity)

            if coupon:
                CouponUsage.objects.get_or_create(
                    coupon=coupon,
                    email=customer.email,
                    order=order,
                )
                Coupon.objects.filter(pk=coupon.pk).update(used_count=F("used_count") + 1)

            self._seed_order_timeline(order, status, created, customer)
            self._seed_payment(order, method, paid, status, created, total)

            Order.objects.filter(pk=order.pk).update(created_at=created, updated_at=created)
            order.refresh_from_db()
            orders.append(order)

        return orders

    @staticmethod
    def _seed_order_timeline(order, status, created, customer):
        flow = [
            Order.Status.PENDING,
            Order.Status.CONFIRMED,
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
            Order.Status.OUT_FOR_DELIVERY,
            Order.Status.DELIVERED,
        ]
        if status == Order.Status.CANCELLED:
            flow = [Order.Status.PENDING, Order.Status.CANCELLED]
        elif status == Order.Status.REFUNDED:
            flow = [Order.Status.PENDING, Order.Status.CONFIRMED, Order.Status.REFUNDED]
        elif status in flow:
            flow = flow[: flow.index(status) + 1]

        step = timedelta(hours=8)
        for offset, state in enumerate(flow):
            event = OrderStatusHistory.objects.create(
                order=order,
                status=state,
                note="Demo order seeded for the Voltiq showcase." if offset == 0 else "",
            )
            event_time = created + step * offset
            OrderStatusHistory.objects.filter(pk=event.pk).update(created_at=event_time)

        updates = {}
        if order.Status.CONFIRMED in flow:
            updates["confirmed_at"] = created + step
        if order.Status.SHIPPED in flow:
            updates["shipped_at"] = created + step * 3
        if order.Status.DELIVERED in flow:
            updates["delivered_at"] = created + step * 5
        if order.Status.CANCELLED in flow:
            updates["cancelled_at"] = created + step
        if updates:
            Order.objects.filter(pk=order.pk).update(**updates)

    @staticmethod
    def _seed_payment(order, method, paid, status, created, total):
        if status == Order.Status.CANCELLED:
            return
        gateway = method if method in {
            Order.PaymentMethod.ESEWA,
            Order.PaymentMethod.KHALTI,
            Order.PaymentMethod.COD,
            Order.PaymentMethod.BANK,
        } else Payment.Gateway.COD
        payment = Payment.objects.create(
            order=order,
            gateway=gateway,
            amount=total,
            status=Payment.Status.SUCCESS if paid else Payment.Status.PENDING,
            is_verified=paid,
            gateway_ref=f"SEED-{order.order_number}" if paid else "",
            gateway_payload={"seed": True, "mode": "demo"},
            verification_payload={"verified_by": "seed_store"} if paid else {},
            completed_at=created + timedelta(hours=2) if paid else None,
            attempt_number=1,
        )
        Payment.objects.filter(pk=payment.pk).update(
            initiated_at=created,
            updated_at=created + timedelta(hours=1),
        )

    def _seed_reviews(self, orders, products, users):
        delivered = [o for o in orders if o.status == Order.Status.DELIVERED]
        counter = 0
        for order in delivered:
            for item in order.items.all():
                if not item.product:
                    continue
                rating = [5, 5, 4, 4, 5][counter % 5]
                Review.objects.get_or_create(
                    product=item.product,
                    user=order.user,
                    defaults={
                        "rating": rating,
                        "title": REVIEW_TITLES[counter % len(REVIEW_TITLES)],
                        "body": REVIEW_BODIES[counter % len(REVIEW_BODIES)],
                        "is_verified_purchase": True,
                        "is_approved": True,
                        "helpful_count": (counter * 3) % 17,
                    },
                )
                counter += 1

        for sku, email, rating, title, body in EXTRA_REVIEWS:
            product = products.get(sku)
            user = users.get(email)
            if not product or not user:
                continue
            review, _ = Review.objects.get_or_create(
                product=product,
                user=user,
                defaults={
                    "rating": rating,
                    "title": title,
                    "body": body,
                    "is_verified_purchase": False,
                    "is_approved": True,
                    "helpful_count": (rating * 4) % 13,
                },
            )
            if sku == "HP-SPECTRE-14":
                review.is_approved = False
                review.save(update_fields=["is_approved", "updated_at"])

    def _seed_wishlist(self, products, users):
        customer = users.get("aarav.sharma@example.com")
        if not customer:
            return
        wishlist, _ = Wishlist.objects.get_or_create(user=customer)
        for sku in ("APL-IP15PRO", "SON-PS5-SLIM", "LG-27GP850"):
            product = products.get(sku)
            if product:
                WishlistItem.objects.get_or_create(wishlist=wishlist, product=product)

    def _seed_newsletter(self):
        for email, name, source, active in NEWSLETTER:
            NewsletterSubscription.objects.update_or_create(
                email=email,
                defaults={"name": name, "source": source, "is_active": active},
            )

    def _seed_messages(self):
        for name, email, phone, subject, message, status in CONTACT_MESSAGES:
            ContactMessage.objects.get_or_create(
                email=email,
                subject=subject,
                defaults={"name": name, "phone": phone, "message": message, "status": status},
            )

    def _seed_notifications(self, users, orders):
        customer = users.get("aarav.sharma@example.com")
        if not customer:
            return
        entries = [
            ("Welcome to Voltiq", "Thanks for joining. Your first-order coupon WELCOME10 is waiting at checkout.", Notification.Kind.ACCOUNT),
            ("Payment successful", "We received your payment for order %s." % (orders[0].order_number if orders else "VQ-DEMO"), Notification.Kind.PAYMENT),
            ("Order delivered", "Your Voltiq order has been delivered. We would love your review.", Notification.Kind.ORDER),
        ]
        for title, message, kind in entries:
            if not Notification.objects.filter(user=customer, title=title).exists():
                Notification.push(customer, title, message, url="", kind=kind)

    def _seed_site_settings(self):
        site = SiteSetting.load()
        site.facebook_url = site.facebook_url or "https://facebook.com/voltiqnp"
        site.instagram_url = site.instagram_url or "https://instagram.com/voltiqnp"
        site.youtube_url = site.youtube_url or "https://youtube.com/@voltiq"
        site.tiktok_url = site.tiktok_url or "https://tiktok.com/@voltiq"
        site.save()

    @staticmethod
    def _cache_clear():
        from django.core.cache import cache

        cache.delete("nav_categories")
        cache.delete("site_setting")
