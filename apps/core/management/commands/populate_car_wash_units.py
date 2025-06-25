# Updated management command with database table check
# Save this as: management/commands/populate_car_wash_units.py

from django.core.management.base import BaseCommand
from django.db import connection
from apps.inventory.models import Unit

class Command(BaseCommand):
    help = 'Populate the database with car wash industry units of measurement'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing units before adding new ones',
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing units with new descriptions',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating units',
        )

    def handle(self, *args, **options):
        # Check if the Unit table exists
        if not self.table_exists():
            self.stdout.write(
                self.style.ERROR(
                    'Unit table does not exist! Please run migrations first:\n'
                    '  python manage.py makemigrations inventory\n'
                    '  python manage.py migrate'
                )
            )
            return

        # Car wash units data
        units_data = [
            # ===== LIQUIDS & CHEMICALS =====
            {"name": "Milliliter", "abbreviation": "ml", "description": "Small liquid measurements for concentrates and additives"},
            {"name": "Centiliter", "abbreviation": "cl", "description": "Small liquid measurements for samples and testing"},
            {"name": "Liter", "abbreviation": "L", "description": "Standard liquid measurement for chemicals and soaps"},
            {"name": "Gallon (US)", "abbreviation": "gal", "description": "Common liquid measurement for bulk chemicals in US"},
            {"name": "Gallon (Imperial)", "abbreviation": "gal UK", "description": "UK/Canadian liquid measurement for bulk chemicals"},
            {"name": "Fluid Ounce (US)", "abbreviation": "fl oz", "description": "Small liquid measurements for concentrates"},
            {"name": "Fluid Ounce (UK)", "abbreviation": "fl oz UK", "description": "Imperial small liquid measurements"},
            {"name": "Quart (US)", "abbreviation": "qt", "description": "Medium liquid measurement for chemicals"},
            {"name": "Pint (US)", "abbreviation": "pt", "description": "Small to medium liquid measurement"},
            
            # Container Sizes
            {"name": "Barrel", "abbreviation": "bbl", "description": "Large chemical containers, 55 gallons"},
            {"name": "Drum", "abbreviation": "drm", "description": "Standard chemical drum, typically 55 gallons"},
            {"name": "Tote", "abbreviation": "tote", "description": "Intermediate bulk container, 250-350 gallons"},
            {"name": "Tank", "abbreviation": "tank", "description": "Bulk storage tank for chemicals"},
            {"name": "Jug", "abbreviation": "jug", "description": "Plastic container, typically 1-5 gallons"},
            {"name": "Bottle", "abbreviation": "btl", "description": "Small containers for concentrates and samples"},
            {"name": "Can", "abbreviation": "can", "description": "Metal containers for chemicals and lubricants"},
            {"name": "Jerrycan", "abbreviation": "jerry", "description": "Portable fuel/chemical container, 5-20 liters"},
            
            # Concentration Measurements
            {"name": "Parts per Million", "abbreviation": "ppm", "description": "Chemical concentration measurement"},
            {"name": "Percentage", "abbreviation": "%", "description": "Chemical concentration as percentage"},
            {"name": "Ratio", "abbreviation": "ratio", "description": "Mixing ratio for chemical dilution"},
            {"name": "Ounces per Gallon", "abbreviation": "oz/gal", "description": "Chemical mixing measurement"},
            {"name": "Milliliters per Liter", "abbreviation": "ml/L", "description": "Metric chemical mixing measurement"},
            
            # ===== SOLID MATERIALS =====
            {"name": "Gram", "abbreviation": "g", "description": "Small weight measurements for additives"},
            {"name": "Kilogram", "abbreviation": "kg", "description": "Standard weight for chemicals and materials"},
            {"name": "Metric Ton", "abbreviation": "t", "description": "Large weight measurements for bulk materials"},
            {"name": "Ounce", "abbreviation": "oz", "description": "Small weight measurements"},
            {"name": "Pound", "abbreviation": "lb", "description": "Standard weight measurement in US"},
            {"name": "Ton (US)", "abbreviation": "tn", "description": "Large weight measurements, 2000 pounds"},
            
            # ===== PACKAGING UNITS =====
            {"name": "Bag", "abbreviation": "bag", "description": "Standard bag packaging for powders and granules"},
            {"name": "Sack", "abbreviation": "sk", "description": "Large bag for bulk materials"},
            {"name": "Pail", "abbreviation": "pail", "description": "Bucket container, typically 5 gallons"},
            {"name": "Bucket", "abbreviation": "bkt", "description": "Container for liquids and pastes"},
            {"name": "Box", "abbreviation": "bx", "description": "Cardboard packaging for various items"},
            {"name": "Case", "abbreviation": "cs", "description": "Multiple units packed together"},
            {"name": "Carton", "abbreviation": "ctn", "description": "Packaging for multiple bottles or containers"},
            {"name": "Crate", "abbreviation": "crt", "description": "Wooden/plastic container for heavy items"},
            {"name": "Pallet", "abbreviation": "plt", "description": "Platform for bulk storage and shipping"},
            
            # ===== TEXTILES & MATERIALS =====
            {"name": "Inch", "abbreviation": "in", "description": "Length measurement for small items"},
            {"name": "Foot", "abbreviation": "ft", "description": "Length measurement for hoses and cables"},
            {"name": "Meter", "abbreviation": "m", "description": "Metric length measurement"},
            {"name": "Yard", "abbreviation": "yd", "description": "Length measurement for fabric materials"},
            {"name": "Square Foot", "abbreviation": "ft²", "description": "Area measurement for covers and mats"},
            {"name": "Square Meter", "abbreviation": "m²", "description": "Metric area measurement"},
            
            # ===== COUNTING UNITS =====
            {"name": "Piece", "abbreviation": "pcs", "description": "Individual items like tools, brushes, nozzles"},
            {"name": "Each", "abbreviation": "ea", "description": "Individual units"},
            {"name": "Pair", "abbreviation": "pr", "description": "Set of two items like gloves or brushes"},
            {"name": "Set", "abbreviation": "set", "description": "Complete set of related items"},
            {"name": "Kit", "abbreviation": "kit", "description": "Collection of tools or supplies"},
            {"name": "Dozen", "abbreviation": "dz", "description": "Set of 12 items"},
            {"name": "Gross", "abbreviation": "gr", "description": "Set of 144 items"},
            {"name": "Hundred", "abbreviation": "C", "description": "Set of 100 items"},
            
            # ===== SPECIALIZED CAR WASH UNITS =====
            {"name": "Brush", "abbreviation": "brsh", "description": "Individual cleaning brush"},
            {"name": "Pad", "abbreviation": "pad", "description": "Cleaning or polishing pad"},
            {"name": "Mitt", "abbreviation": "mitt", "description": "Wash mitt or glove"},
            {"name": "Cloth", "abbreviation": "clth", "description": "Cleaning cloth or rag"},
            {"name": "Towel", "abbreviation": "twl", "description": "Drying towel"},
            {"name": "Chamois", "abbreviation": "cham", "description": "Natural or synthetic chamois"},
            {"name": "Squeegee", "abbreviation": "sqg", "description": "Water removal tool"},
            {"name": "Sponge", "abbreviation": "spg", "description": "Cleaning sponge"},
            
            # Equipment Parts
            {"name": "Filter", "abbreviation": "fltr", "description": "Water or air filter"},
            {"name": "Nozzle", "abbreviation": "nzl", "description": "Spray nozzle or tip"},
            {"name": "Hose", "abbreviation": "hose", "description": "Water or chemical hose"},
            {"name": "Gun", "abbreviation": "gun", "description": "Spray gun or wand"},
            {"name": "Tip", "abbreviation": "tip", "description": "Nozzle tip or spray tip"},
            {"name": "Fitting", "abbreviation": "ftg", "description": "Pipe or hose fitting"},
            {"name": "Valve", "abbreviation": "vlv", "description": "Water or chemical valve"},
            {"name": "Pump", "abbreviation": "pump", "description": "Water or chemical pump"},
            {"name": "Motor", "abbreviation": "mtr", "description": "Equipment motor"},
            {"name": "Belt", "abbreviation": "belt", "description": "Drive belt for equipment"},
            {"name": "Blade", "abbreviation": "bld", "description": "Squeegee blade or scraper"},
            
            # ===== PRESSURE AND FLOW =====
            {"name": "PSI", "abbreviation": "psi", "description": "Pounds per square inch - pressure measurement"},
            {"name": "Bar", "abbreviation": "bar", "description": "Metric pressure measurement"},
            {"name": "GPM", "abbreviation": "gpm", "description": "Gallons per minute - flow rate"},
            {"name": "LPM", "abbreviation": "lpm", "description": "Liters per minute - metric flow rate"},
            {"name": "CFM", "abbreviation": "cfm", "description": "Cubic feet per minute - air flow"},
            
            # ===== ELECTRICAL UNITS =====
            {"name": "Amp", "abbreviation": "A", "description": "Electric current measurement"},
            {"name": "Volt", "abbreviation": "V", "description": "Electric voltage measurement"},
            {"name": "Watt", "abbreviation": "W", "description": "Power consumption measurement"},
            {"name": "Kilowatt", "abbreviation": "kW", "description": "Power measurement for large equipment"},
            {"name": "Horsepower", "abbreviation": "HP", "description": "Motor power measurement"},
            
            # ===== TEMPERATURE =====
            {"name": "Fahrenheit", "abbreviation": "°F", "description": "Temperature measurement"},
            {"name": "Celsius", "abbreviation": "°C", "description": "Metric temperature measurement"},
            
            # ===== TIME-BASED UNITS =====
            {"name": "Second", "abbreviation": "sec", "description": "Time measurement for cycles"},
            {"name": "Minute", "abbreviation": "min", "description": "Time measurement for wash cycles"},
            {"name": "Hour", "abbreviation": "hr", "description": "Time measurement for equipment runtime"},
            {"name": "Cycle", "abbreviation": "cyc", "description": "Complete wash cycle"},
            {"name": "Use", "abbreviation": "use", "description": "Single use of consumable item"},
            
            # ===== DISPENSING UNITS =====
            {"name": "Shot", "abbreviation": "shot", "description": "Single dispensing of chemical"},
            {"name": "Spray", "abbreviation": "spry", "description": "Single spray application"},
            {"name": "Dose", "abbreviation": "dose", "description": "Measured amount of chemical"},
            
            # ===== SPECIALTY MEASUREMENTS =====
            {"name": "pH Unit", "abbreviation": "pH", "description": "Acidity/alkalinity measurement"},
            {"name": "Hardness Grains", "abbreviation": "gpg", "description": "Water hardness measurement"},
            {"name": "TDS", "abbreviation": "TDS", "description": "Total dissolved solids in water"},
            {"name": "Micron", "abbreviation": "μm", "description": "Filter pore size measurement"},
            
            # Usage and Service
            {"name": "Wash", "abbreviation": "wash", "description": "Number of washes a product lasts"},
            {"name": "Car", "abbreviation": "car", "description": "Per-vehicle measurement"},
            {"name": "Application", "abbreviation": "app", "description": "Single application of wax or sealant"},
            {"name": "Treatment", "abbreviation": "trt", "description": "Complete treatment application"},
            
            # ===== QUALITY MEASUREMENTS =====
            {"name": "Gloss Unit", "abbreviation": "GU", "description": "Surface gloss measurement"},
            {"name": "Shine Level", "abbreviation": "shine", "description": "Shine intensity measurement"},
            {"name": "Coverage", "abbreviation": "cov", "description": "Area coverage per unit"},
            
            # ===== COMMERCIAL CAR WASH =====
            {"name": "Bay", "abbreviation": "bay", "description": "Wash bay unit"},
            {"name": "Lane", "abbreviation": "lane", "description": "Wash lane or tunnel"},
            {"name": "Station", "abbreviation": "stn", "description": "Equipment station"},
            
            # ===== SERVICE UNITS =====
            {"name": "Credit", "abbreviation": "cred", "description": "Wash credit or token"},
            {"name": "Token", "abbreviation": "tkn", "description": "Physical or digital wash token"},
            {"name": "Visit", "abbreviation": "visit", "description": "Customer visit count"},
            
            # ===== PACKAGING SIZES =====
            {"name": "Sample", "abbreviation": "smpl", "description": "Small sample size for testing"},
            {"name": "Travel Size", "abbreviation": "trvl", "description": "Small portable container"},
            {"name": "Super Sack", "abbreviation": "ss", "description": "Large bulk bag, 1000+ pounds"},
            {"name": "Roll", "abbreviation": "rl", "description": "Rolled material"},
            {"name": "Reel", "abbreviation": "reel", "description": "Spooled material"},
            {"name": "Coil", "abbreviation": "coil", "description": "Coiled material"},
            {"name": "Bundle", "abbreviation": "bdl", "description": "Bundled items"},
            {"name": "Bale", "abbreviation": "bl", "description": "Compressed bundle"},
        ]

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No units will be created'))

        if options['clear'] and not options['dry_run']:
            Unit.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared all existing units'))

        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for unit_data in units_data:
            try:
                if options['dry_run']:
                    existing = Unit.objects.filter(abbreviation=unit_data['abbreviation']).exists()
                    if existing:
                        self.stdout.write(
                            self.style.HTTP_INFO(f'[DRY RUN] Would skip: {unit_data["name"]} ({unit_data["abbreviation"]}) - already exists')
                        )
                        skipped_count += 1
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(f'[DRY RUN] Would create: {unit_data["name"]} ({unit_data["abbreviation"]})')
                        )
                        created_count += 1
                    continue
                
                unit, created = Unit.objects.get_or_create(
                    abbreviation=unit_data['abbreviation'],
                    defaults={
                        'name': unit_data['name'],
                        'description': unit_data['description'],
                        'is_active': True
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created: {unit.name} ({unit.abbreviation})')
                    )
                elif options['update']:
                    # Update description if different
                    if unit.description != unit_data['description'] or unit.name != unit_data['name']:
                        unit.description = unit_data['description']
                        unit.name = unit_data['name']
                        unit.save()
                        updated_count += 1
                        self.stdout.write(
                            self.style.WARNING(f'↻ Updated: {unit.name} ({unit.abbreviation})')
                        )
                    else:
                        skipped_count += 1
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.HTTP_INFO(f'- Exists: {unit.name} ({unit.abbreviation})')
                    )
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'✗ Error with {unit_data["name"]}: {str(e)}')
                )
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS(
                f'SUMMARY:\n'
                f'• Total units processed: {len(units_data)}\n'
                f'• Created: {created_count}\n'
                f'• Updated: {updated_count}\n'
                f'• Skipped: {skipped_count}\n'
                f'• Errors: {error_count}'
            )
        )
        
        # Only show total count if not dry run and no errors
        if not options['dry_run'] and error_count == 0:
            try:
                total_units = Unit.objects.count()
                self.stdout.write(f'• Total units in database: {total_units}')
            except Exception:
                self.stdout.write('• Could not get total count from database')
        
        if not options['dry_run']:
            # Show categories
            categories = {
                'Liquids & Chemicals': ['ml', 'L', 'gal', 'bbl', 'tote', 'ppm', '%'],
                'Solids & Materials': ['kg', 'lb', 'bag', 'pail', 'bx'],
                'Counting Units': ['pcs', 'ea', 'set', 'dz', 'pr'],
                'Equipment Parts': ['fltr', 'nzl', 'pump', 'mtr', 'gun'],
                'Measurements': ['psi', 'gpm', 'pH', '°F', 'A', 'V'],
                'Specialty': ['wash', 'car', 'app', 'cyc'],
                'Textiles': ['twl', 'clth', 'mitt', 'pad', 'cham'],
                'Service': ['bay', 'lane', 'visit', 'cred', 'tkn']
            }
            
            self.stdout.write('\n' + self.style.SUCCESS('Unit Categories:'))
            for category, abbrevs in categories.items():
                try:
                    count = Unit.objects.filter(abbreviation__in=abbrevs).count()
                    self.stdout.write(f'  {category}: {count} units')
                except Exception:
                    self.stdout.write(f'  {category}: Could not count units')
        
        if options['dry_run']:
            self.stdout.write('\n' + self.style.WARNING('This was a dry run. Use without --dry-run to actually create units.'))
        else:
            self.stdout.write('\n' + self.style.SUCCESS('Car wash units setup complete!'))
            self.stdout.write(
                'You can now use these units when creating inventory items.\n'
                'To see all units, visit the Units page in your inventory management.'
            )

    def table_exists(self):
        """Check if the Unit table exists in the database"""
        try:
            with connection.cursor() as cursor:
                table_names = connection.introspection.table_names(cursor)
                # Check for different possible table names
                unit_table_names = [
                    'inventory_unit',  # Standard Django naming
                    'units',           # Custom naming
                    f'{Unit._meta.app_label}_{Unit._meta.model_name}'  # Dynamic naming
                ]
                return any(table_name in table_names for table_name in unit_table_names)
        except Exception:
            return False