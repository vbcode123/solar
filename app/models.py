from django.db import models

# Agent Model: Stores agent information for the Solar project
class Agent(models.Model):
    # Agent's full name
    name = models.CharField(max_length=100)
    # Unique email address for each agent
    email = models.EmailField(unique=True)
    # Unique phone number used for login
    phone = models.CharField(max_length=15, unique=True)
    # Physical address
    address = models.TextField(null=True, blank=True)
    # Profile photo
    profile_photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    # Aadhar number (formatted with spaces)
    aadhar_number = models.CharField(max_length=15, null=True, blank=True)
    # Aadhar card image
    aadhar_card_image = models.ImageField(upload_to='aadhar_cards/', null=True, blank=True)
    # Plain text password (for demonstration)
    password = models.CharField(max_length=100)
    # Access control: If False, agent cannot login
    is_active = models.BooleanField(default=True)
    # Last seen for chat
    last_seen = models.DateTimeField(null=True, blank=True)
    # Commission amount per customer (admin can set this)
    commission_per_customer = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=20.00)
    # Automatic timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# Customer Model: Stores customer details and documents submitted by Agents
class Customer(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Confirmed', 'Confirmed'),
        ('Rejected', 'Rejected'),
    ]
    
    VENDOR_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approve', 'Approve'),
        ('Complete', 'Complete'),
        ('Hold', 'Hold'),
    ]

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='customers')
    customer_name = models.CharField(max_length=200)
    
    # Documents
    aadhaar_card = models.FileField(upload_to='customers/aadhaar/')
    pan_card = models.FileField(upload_to='customers/pan/')
    electricity_bill = models.FileField(upload_to='customers/bills/')
    bank_document = models.FileField(upload_to='customers/bank/')
    roof_photo = models.FileField(upload_to='customers/roof/')
    meter_photo = models.FileField(upload_to='customers/meter/')
    passport_photo = models.FileField(upload_to='customers/photos/')
    ownership_proof = models.FileField(upload_to='customers/ownership/')
    vendor_quotation = models.FileField(upload_to='customers/quotations/')
    
    mobile_number = models.CharField(max_length=15)
    address = models.TextField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    remark = models.TextField(null=True, blank=True)
    status_updated_by_name = models.CharField(max_length=255, null=True, blank=True)
    status_updated_by_role = models.CharField(max_length=20, null=True, blank=True)
    
    # Vendor Assignment Fields
    vendor = models.ForeignKey('Vendor', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_customers')
    vendor_remark = models.TextField(null=True, blank=True)
    assigned_to_vendor_at = models.DateTimeField(null=True, blank=True)
    
    # Vendor Status Fields
    vendor_status = models.CharField(max_length=20, choices=VENDOR_STATUS_CHOICES, default='Pending')
    vendor_status_remark = models.TextField(null=True, blank=True)
    vendor_status_updated_at = models.DateTimeField(null=True, blank=True)
    
    # Extra Payment Fields
    extra_payment_done = models.BooleanField(default=False)
    extra_payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Vendor Document Payment Fields
    vendor_doc_payment_done = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.customer_name

# Payment Model: Tracks payments made by admin to agents
class Payment(models.Model):
    PAYMENT_METHODS = [
        ('UPI', 'UPI'),
        ('Cash', 'Cash'),
    ]
    PAYMENT_TYPES = [
        ('Regular', 'Regular Commission'),
        ('Extra', 'Extra Commission'),
    ]

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default='Regular')
    utr_number = models.CharField(max_length=50, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    remark = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.agent.name} - {self.amount} ({self.payment_type})"

# Vendor Model: Stores vendor information for the Solar project
class Vendor(models.Model):
    # Unique Vendor Code (Auto-generated)
    vendor_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    # Vendor's full name
    name = models.CharField(max_length=100)
    # Company name
    company_name = models.CharField(max_length=200)
    # Unique phone number used for login
    phone = models.CharField(max_length=15, unique=True)
    # Physical address
    address = models.TextField(null=True, blank=True)
    # Profile photo
    profile_photo = models.ImageField(upload_to='vendor_photos/', null=True, blank=True)
    # Plain text password
    password = models.CharField(max_length=100)
    # Access control
    is_active = models.BooleanField(default=True)
    # Last seen for chat
    last_seen = models.DateTimeField(null=True, blank=True)
    # Automatic timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.vendor_code:
            last_vendor = Vendor.objects.all().order_by('id').last()
            if not last_vendor:
                self.vendor_code = 'VND0001'
            else:
                last_id = last_vendor.id
                self.vendor_code = 'VND' + str(last_id + 1).zfill(4)
        super(Vendor, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.company_name})"

# Vendor Document Payment Model: Tracks payments made by vendors to admin for document approval
class VendorDocumentPayment(models.Model):
    PAYMENT_METHODS = [
        ('UPI', 'UPI'),
        ('Cash', 'Cash'),
    ]

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='document_payments')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='vendor_doc_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    utr_number = models.CharField(max_length=50, null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    remark = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.vendor.name} - {self.customer.customer_name} - {self.amount}"

# Customer Status History Model: Tracks all status changes
class CustomerStatusHistory(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20)
    changed_by_name = models.CharField(max_length=255)
    changed_by_role = models.CharField(max_length=20)  # 'Admin' or 'Vendor'
    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.customer_name} - {self.status} by {self.changed_by_name} ({self.created_at.strftime('%d %b %Y %H:%M')})"

# Chat Message Model: For admin-vendor communication
class ChatMessage(models.Model):
    SENDER_CHOICES = [
        ('Admin', 'Admin'),
        ('Vendor', 'Vendor'),
    ]

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to='chat_images/', null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender} to {self.vendor.name} - {self.created_at.strftime('%d %b %Y %H:%M')}"

# Agent Chat Message Model: For admin-agent communication
class AgentChatMessage(models.Model):
    SENDER_CHOICES = [
        ('Admin', 'Admin'),
        ('Agent', 'Agent'),
    ]

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to='agent_chat_images/', null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender} to {self.agent.name} - {self.created_at.strftime('%d %b %Y %H:%M')}"
