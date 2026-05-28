from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from .models import Agent, Customer, Payment, Vendor, ChatMessage, VendorDocumentPayment
from django.db.models import Q, Count, Sum, Max
from django.utils import timezone
from datetime import timedelta
import zipfile
import io
from django.http import HttpResponse, JsonResponse

# ==========================================
# ADMIN COMMISSION & PAYMENT SYSTEM
# ==========================================

# Agent Commissions: List of all agents with their earnings
def agent_commissions(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    agents_data = []
    agents = Agent.objects.all()
    
    for agent in agents:
        # Count approved and confirmed customers (both give 20 rupees commission)
        approved_count = Customer.objects.filter(agent=agent, status__in=['Approved', 'Confirmed']).count()
        # Count only confirmed (completed) customers for extra payouts
        confirmed_count = Customer.objects.filter(agent=agent, status='Confirmed').count()
        
        # Calculate regular earnings (20 rupees per approved/confirmed customer)
        regular_earnings = approved_count * 20
        # Calculate total regular payments made
        total_paid_regular = Payment.objects.filter(agent=agent, payment_type='Regular').aggregate(Sum('amount'))['amount__sum'] or 0
        # Calculate total extra payments made
        total_paid_extra = Payment.objects.filter(agent=agent, payment_type='Extra').aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Total combined earnings
        total_combined_earnings = float(regular_earnings) + float(total_paid_extra)
        
        # Remaining regular balance
        balance = regular_earnings - float(total_paid_regular)
        
        agents_data.append({
            'agent': agent,
            'approved_count': approved_count,
            'confirmed_count': confirmed_count,
            'total_earnings': regular_earnings,
            'total_paid_regular': total_paid_regular,
            'total_paid_extra': total_paid_extra,
            'total_combined_earnings': total_combined_earnings,
            'balance': balance
        })
        
    return render(request, 'admin/agent_commissions.html', {'agents_data': agents_data})

# Process Regular Payment
def agent_payment(request, agent_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    agent = get_object_or_404(Agent, id=agent_id)
    payments = Payment.objects.filter(agent=agent, payment_type='Regular').order_by('-date')
    
    # Calculate stats (Approved + Confirmed counts for base commission)
    approved_count = Customer.objects.filter(agent=agent, status__in=['Approved', 'Confirmed']).count()
    total_earnings = approved_count * 20
    total_paid = Payment.objects.filter(agent=agent, payment_type='Regular').aggregate(Sum('amount'))['amount__sum'] or 0
    balance = total_earnings - float(total_paid)

    if request.method == 'POST':
        amount = request.POST.get('amount')
        method = request.POST.get('method')
        utr_number = request.POST.get('utr_number')
        remark = request.POST.get('remark')
        
        if float(amount) <= 0:
            messages.error(request, "Amount must be greater than 0")
        else:
            Payment.objects.create(
                agent=agent,
                amount=amount,
                method=method,
                payment_type='Regular',
                utr_number=utr_number if method == 'UPI' else None,
                remark=remark
            )
            messages.success(request, f"Regular Payment of ₹{amount} recorded for {agent.name}")
            return redirect('agent_payment', agent_id=agent.id)
            
    return render(request, 'admin/agent_payment.html', {
        'agent': agent,
        'payments': payments,
        'approved_count': approved_count,
        'total_earnings': total_earnings,
        'total_paid': total_paid,
        'balance': balance
    })

# Extra Commissions: List of agents with "Confirmed" (Complete) applications
def extra_commissions(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    agents_data = []
    agents = Agent.objects.all()
    
    for agent in agents:
        # Count confirmed (complete) customers
        confirmed_count = Customer.objects.filter(agent=agent, status='Confirmed').count()
        # Admin decides payment, but we can show how many are confirmed
        total_paid = Payment.objects.filter(agent=agent, payment_type='Extra').aggregate(Sum('amount'))['amount__sum'] or 0
        
        agents_data.append({
            'agent': agent,
            'confirmed_count': confirmed_count,
            'total_paid': total_paid,
        })
        
    return render(request, 'admin/extra_commissions.html', {'agents_data': agents_data})

# Process Extra Payment
def extra_payment(request, agent_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    agent = get_object_or_404(Agent, id=agent_id)
    payments = Payment.objects.filter(agent=agent, payment_type='Extra').order_by('-date')
    
    confirmed_count = Customer.objects.filter(agent=agent, status='Confirmed').count()
    total_paid = Payment.objects.filter(agent=agent, payment_type='Extra').aggregate(Sum('amount'))['amount__sum'] or 0

    if request.method == 'POST':
        amount = request.POST.get('amount')
        method = request.POST.get('method')
        utr_number = request.POST.get('utr_number')
        remark = request.POST.get('remark')
        
        if float(amount) <= 0:
            messages.error(request, "Amount must be greater than 0")
        else:
            Payment.objects.create(
                agent=agent,
                amount=amount,
                method=method,
                payment_type='Extra',
                utr_number=utr_number if method == 'UPI' else None,
                remark=remark
            )
            # Mark all confirmed customers as extra payment done
            Customer.objects.filter(agent=agent, status='Confirmed').update(extra_payment_done=True)
            messages.success(request, f"Extra Commission of ₹{amount} paid to {agent.name}")
            return redirect('extra_payment', agent_id=agent.id)
            
    return render(request, 'admin/extra_payment.html', {
        'agent': agent,
        'payments': payments,
        'confirmed_count': confirmed_count,
        'total_paid': total_paid,
    })

# Individual Customer Extra Payment
def customer_extra_payment(request, customer_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    customer = get_object_or_404(Customer, id=customer_id)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        method = request.POST.get('method')
        utr_number = request.POST.get('utr_number')
        remark = request.POST.get('remark')
        
        if float(amount) <= 0:
            messages.error(request, "Amount must be greater than 0")
        else:
            # Create payment
            Payment.objects.create(
                agent=customer.agent,
                amount=amount,
                method=method,
                payment_type='Extra',
                utr_number=utr_number if method == 'UPI' else None,
                remark=remark
            )
            # Mark this specific customer as extra payment done
            customer.extra_payment_done = True
            customer.extra_payment_amount = amount
            customer.save()
            
            messages.success(request, f"Extra Commission of ₹{amount} paid for {customer.customer_name}")
            return redirect('all_customers_list')
    
    return render(request, 'admin/customer_extra_payment.html', {
        'customer': customer
    })

# ==========================================
# LOGOUT SYSTEM
# ==========================================

# Home Page: Landing page for the project
def home(request):
    return render(request, 'home.html')

# Admin Login: Handles Django superuser authentication
def admin_login(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        # Authenticate using Django default auth system
        user = authenticate(username=u, password=p)
        if user is not None and user.is_staff:
            login(request, user)
            messages.success(request, "Admin Login Successful!")
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Invalid Credentials or Not an Admin!")
    return render(request, 'admin_login.html')

# Agent Login: Handles custom Agent model authentication
def agent_login(request):
    if request.method == 'POST':
        ph = request.POST.get('phone').replace(" ", "")
        p = request.POST.get('password')
        try:
            # Check if agent exists with provided phone and password
            agent = Agent.objects.get(phone=ph, password=p)
            # Check if access is enabled
            if not agent.is_active:
                messages.error(request, "Your access is disabled. Please contact admin!")
                return redirect('agent_login')
                
            # Store agent info in session
            request.session['agent_id'] = agent.id
            request.session['agent_name'] = agent.name
            messages.success(request, f"Welcome {agent.name}!")
            return redirect('agent_dashboard')
        except Agent.DoesNotExist:
            messages.error(request, "Invalid Phone or Password!")
    return render(request, 'agent_login.html')

# ==========================================
# ADMIN PROTECTED VIEWS
# ==========================================

# Admin Dashboard: Shows statistics and quick actions
def admin_dashboard(request):
    # Security check: Ensure user is logged in as staff
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    total_agents = Agent.objects.count()
    total_customers = Customer.objects.count()
    approved_customers = Customer.objects.filter(status='Approved').count()
    confirmed_customers = Customer.objects.filter(status='Confirmed').count()
    pending_customers = Customer.objects.filter(status='Pending').count()
    
    # Get unread messages count for chat notifications
    unread_messages_count = ChatMessage.objects.filter(sender='Vendor', is_read=False).count()
    
    # Day-wise Report (Last 7 Days)
    day_wise_report = []
    today = timezone.now().date()
    for i in range(7):
        date = today - timedelta(days=i)
        count = Customer.objects.filter(created_at__date=date).count()
        day_wise_report.append({
            'date': date,
            'count': count
        })
    
    context = {
        'total_agents': total_agents,
        'total_customers': total_customers,
        'approved_customers': approved_customers,
        'confirmed_customers': confirmed_customers,
        'pending_customers': pending_customers,
        'day_wise_report': day_wise_report,
        'unread_messages_count': unread_messages_count
    }
    return render(request, 'admin/dashboard.html', context)

# All Customers List: View all customers with optional status filtering
def all_customers_list(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    status_filter = request.GET.get('status')
    search_query = request.GET.get('search')
    
    customers = Customer.objects.all().order_by('-created_at')
    
    if status_filter:
        customers = customers.filter(status=status_filter)
    
    if search_query:
        customers = customers.filter(
            Q(customer_name__icontains=search_query) | 
            Q(mobile_number__icontains=search_query) |
            Q(agent__name__icontains=search_query)
        )
        
    return render(request, 'admin/all_customers_list.html', {
        'customers': customers,
        'status_filter': status_filter,
        'search_query': search_query
    })

# Add Agent: Form to register new agents
def add_agent(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    if request.method == 'POST':
        n = request.POST.get('name')
        e = request.POST.get('email')
        ph = request.POST.get('phone').replace(" ", "")
        addr = request.POST.get('address')
        an = request.POST.get('aadhar_number')
        p = request.POST.get('password')
        cp = request.POST.get('confirm_password')
        commission = request.POST.get('commission_per_customer')
        
        # Files
        photo = request.FILES.get('profile_photo')
        aadhar_img = request.FILES.get('aadhar_card_image')

        # Validation checks
        if p != cp:
            messages.error(request, "Passwords do not match!")
        elif Agent.objects.filter(email=e).exists():
            messages.error(request, "Email already exists!")
        elif Agent.objects.filter(phone=ph).exists():
            messages.error(request, "Phone number already exists!")
        else:
            # Create agent record with new fields
            Agent.objects.create(
                name=n, 
                email=e, 
                phone=ph, 
                address=addr,
                aadhar_number=an,
                profile_photo=photo,
                aadhar_card_image=aadhar_img,
                password=p,
                commission_per_customer=commission
            )
            messages.success(request, "Agent added successfully!")
            return redirect('agent_list')
    return render(request, 'admin/add_agent.html')

# Agent List: Display all agents with search and actions
def agent_list(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    query = request.GET.get('search')
    if query:
        # Search by name, email, or phone
        agents = Agent.objects.filter(
            Q(name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query)
        ).order_by('-created_at')
    else:
        agents = Agent.objects.all().order_by('-created_at')
        
    return render(request, 'admin/agent_list.html', {'agents': agents})

# View Agent: Show full details of an agent
def view_agent(request, id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    agent = get_object_or_404(Agent, id=id)
    return render(request, 'admin/view_agent.html', {'agent': agent})

# Toggle Agent Access: Enable or disable login access
def toggle_access(request, id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    agent = get_object_or_404(Agent, id=id)
    agent.is_active = not agent.is_active
    agent.save()
    status = "Enabled" if agent.is_active else "Disabled"
    messages.info(request, f"Access for {agent.name} has been {status}.")
    return redirect('agent_list')

# Edit Agent: Update existing agent information
def edit_agent(request, id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    agent = get_object_or_404(Agent, id=id)
    if request.method == 'POST':
        agent.name = request.POST.get('name')
        agent.email = request.POST.get('email')
        agent.phone = request.POST.get('phone').replace(" ", "")
        agent.address = request.POST.get('address')
        agent.aadhar_number = request.POST.get('aadhar_number')
        agent.password = request.POST.get('password')
        agent.commission_per_customer = request.POST.get('commission_per_customer')
        
        # Update photos if provided
        if request.FILES.get('profile_photo'):
            agent.profile_photo = request.FILES.get('profile_photo')
        if request.FILES.get('aadhar_card_image'):
            agent.aadhar_card_image = request.FILES.get('aadhar_card_image')
            
        agent.save()
        messages.success(request, "Agent updated successfully!")
        return redirect('agent_list')
    return render(request, 'admin/edit_agent.html', {'agent': agent})

# Vendor Management (Admin Side)

def add_vendor(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    if request.method == 'POST':
        v_code = request.POST.get('vendor_code')
        name = request.POST.get('name')
        company = request.POST.get('company_name')
        phone = request.POST.get('phone').replace(" ", "")
        address = request.POST.get('address')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        photo = request.FILES.get('profile_photo')

        if password != confirm_password:
            messages.error(request, "Passwords do not match!")
        elif Vendor.objects.filter(phone=phone).exists():
            messages.error(request, "Phone number already exists!")
        else:
            Vendor.objects.create(
                vendor_code=v_code if v_code else None,
                name=name,
                company_name=company,
                phone=phone,
                address=address,
                password=password,
                profile_photo=photo
            )
            messages.success(request, "Vendor added successfully!")
            return redirect('vendor_list')
    return render(request, 'admin/add_vendor.html')

def vendor_list(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    vendors = Vendor.objects.all().annotate(
        unread_count=Count('chat_messages', filter=Q(chat_messages__sender='Vendor', chat_messages__is_read=False))
    ).order_by('-created_at')
    unread_messages_count = ChatMessage.objects.filter(sender='Vendor', is_read=False).count()
    return render(request, 'admin/vendor_list.html', {'vendors': vendors, 'unread_messages_count': unread_messages_count})

def view_vendor(request, id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    vendor = get_object_or_404(Vendor, id=id)
    return render(request, 'admin/view_vendor.html', {'vendor': vendor})

def edit_vendor(request, id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    vendor = get_object_or_404(Vendor, id=id)
    if request.method == 'POST':
        vendor.vendor_code = request.POST.get('vendor_code')
        vendor.name = request.POST.get('name')
        vendor.company_name = request.POST.get('company_name')
        vendor.phone = request.POST.get('phone').replace(" ", "")
        vendor.address = request.POST.get('address')
        vendor.password = request.POST.get('password')
        if request.FILES.get('profile_photo'):
            vendor.profile_photo = request.FILES.get('profile_photo')
        vendor.save()
        messages.success(request, "Vendor details updated!")
        return redirect('vendor_list')
    return render(request, 'admin/edit_vendor.html', {'vendor': vendor})

def delete_vendor(request, id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    vendor = get_object_or_404(Vendor, id=id)
    vendor.delete()
    messages.success(request, "Vendor deleted successfully!")
    return redirect('vendor_list')

def vendor_login(request):
    if request.method == 'POST':
        ph = request.POST.get('phone').replace(" ", "")
        p = request.POST.get('password')
        try:
            vendor = Vendor.objects.get(phone=ph, password=p)
            if vendor.is_active:
                request.session['vendor_id'] = vendor.id
                request.session['vendor_name'] = vendor.name
                return redirect('vendor_dashboard')
            else:
                messages.error(request, "Your account is disabled. Contact Admin.")
        except Vendor.DoesNotExist:
            messages.error(request, "Invalid Phone or Password!")
    return render(request, 'vendor_login.html')

def vendor_dashboard(request):
    vendor_id = request.session.get('vendor_id')
    if not vendor_id:
        return redirect('vendor_login')
    try:
        vendor = Vendor.objects.get(id=vendor_id)
    except Vendor.DoesNotExist:
        # Clear invalid session and redirect to login
        if 'vendor_id' in request.session:
            del request.session['vendor_id']
        if 'vendor_name' in request.session:
            del request.session['vendor_name']
        messages.error(request, "Invalid session! Please login again.")
        return redirect('vendor_login')
    
    # Fetch assigned installation jobs
    assigned_jobs = Customer.objects.filter(vendor=vendor).order_by('-assigned_to_vendor_at')
    
    # Get unread messages count for chat notifications
    unread_messages_count = ChatMessage.objects.filter(vendor=vendor, sender='Admin', is_read=False).count()
    
    context = {
        'vendor': vendor,
        'assigned_jobs': assigned_jobs,
        'total_jobs': assigned_jobs.count(),
        'pending_jobs': assigned_jobs.filter(vendor_status='Pending').count(),
        'approve_jobs': assigned_jobs.filter(vendor_status='Approve').count(),
        'hold_jobs': assigned_jobs.filter(vendor_status='Hold').count(),
        'completed_jobs': assigned_jobs.filter(vendor_status='Complete').count(),
        'unread_messages_count': unread_messages_count
    }
    
    return render(request, 'vendor/dashboard.html', context)

def vendor_logout(request):
    if 'vendor_id' in request.session:
        del request.session['vendor_id']
    if 'vendor_name' in request.session:
        del request.session['vendor_name']
    return redirect('vendor_login')

# ==========================================
# VENDOR JOB MANAGEMENT
# ==========================================

def vendor_installation_jobs(request):
    vendor_id = request.session.get('vendor_id')
    if not vendor_id:
        return redirect('vendor_login')
    vendor = get_object_or_404(Vendor, id=vendor_id)
    
    # Get all assigned jobs
    jobs = Customer.objects.filter(vendor=vendor).order_by('-assigned_to_vendor_at')
    
    # Get unread messages count for chat notifications
    unread_messages_count = ChatMessage.objects.filter(vendor=vendor, sender='Admin', is_read=False).count()
    
    context = {
        'vendor': vendor,
        'jobs': jobs,
        'unread_messages_count': unread_messages_count
    }
    
    return render(request, 'vendor/installation_jobs.html', context)

def vendor_job_details(request, cust_id):
    vendor_id = request.session.get('vendor_id')
    if not vendor_id:
        return redirect('vendor_login')
    vendor = get_object_or_404(Vendor, id=vendor_id)
    customer = get_object_or_404(Customer, id=cust_id, vendor=vendor)
    
    # Get unread messages count for chat notifications
    unread_messages_count = ChatMessage.objects.filter(vendor=vendor, sender='Admin', is_read=False).count()
    
    return render(request, 'vendor/job_details.html', {'vendor': vendor, 'customer': customer, 'unread_messages_count': unread_messages_count})

def update_vendor_status(request, cust_id):
    vendor_id = request.session.get('vendor_id')
    if not vendor_id:
        return redirect('vendor_login')
    vendor = get_object_or_404(Vendor, id=vendor_id)
    customer = get_object_or_404(Customer, id=cust_id, vendor=vendor)
    
    # Prevent status change if job is already confirmed or rejected
    if customer.status == 'Confirmed':
        messages.error(request, "Cannot update status - job is already confirmed!")
        return redirect('vendor_installation_jobs')
    if customer.status == 'Rejected':
        messages.error(request, "Cannot update status - job is currently rejected!")
        return redirect('vendor_installation_jobs')
    
    if request.method == 'POST':
        vendor_status = request.POST.get('vendor_status')
        remark = request.POST.get('vendor_status_remark')
        
        if vendor_status:
            customer.vendor_status = vendor_status
            customer.vendor_status_remark = remark
            customer.vendor_status_updated_at = timezone.now()
            
            # Map vendor status to customer status
            if vendor_status == 'Pending':
                new_status = 'Pending'
            elif vendor_status == 'Approve':
                new_status = 'Approved'
            elif vendor_status == 'Complete':
                new_status = 'Confirmed'
            elif vendor_status == 'Hold':
                new_status = 'Rejected'
                
            # Update customer status
            customer.status = new_status
                
            # Set who updated the status
            customer.status_updated_by_name = vendor.company_name
            customer.status_updated_by_role = "Vendor"
                
            customer.save()
            
            # Save to status history
            from app.models import CustomerStatusHistory
            CustomerStatusHistory.objects.create(
                customer=customer,
                status=new_status,
                changed_by_name=vendor.company_name,
                changed_by_role="Vendor",
                remark=remark
            )
            
            messages.success(request, f"Job status updated!")
        else:
            messages.error(request, "Please select a status!")
            
    return redirect('vendor_installation_jobs')

# Delete Agent: Remove agent record from database
def delete_agent(request, id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    agent = get_object_or_404(Agent, id=id)
    agent.delete()
    messages.success(request, "Agent deleted successfully!")
    return redirect('agent_list')

# ==========================================
# AGENT PROTECTED VIEWS
# ==========================================

# Agent Dashboard: Private area for agents
def agent_dashboard(request):
    # Security check: Ensure agent session exists
    agent_id = request.session.get('agent_id')
    if not agent_id:
        return redirect('agent_login')
    agent = get_object_or_404(Agent, id=agent_id)
    
    # Statistics for dashboard
    total_apps = Customer.objects.filter(agent=agent).count()
    approved_count = Customer.objects.filter(agent=agent, status__in=['Approved', 'Confirmed']).count() # Count both for commission
    confirmed_count = Customer.objects.filter(agent=agent, status='Confirmed').count()
    rejected_count = Customer.objects.filter(agent=agent, status='Rejected').count()
    
    # Earnings calculation
    regular_earnings = approved_count * 20
    total_paid_extra = Payment.objects.filter(agent=agent, payment_type='Extra').aggregate(Sum('amount'))['amount__sum'] or 0
    total_combined_earnings = float(regular_earnings) + float(total_paid_extra)
    
    context = {
        'agent': agent,
        'total_apps': total_apps,
        'approved_count': approved_count,
        'confirmed_count': confirmed_count,
        'rejected_count': rejected_count,
        'total_combined_earnings': total_combined_earnings,
        'regular_earnings': regular_earnings,
        'extra_earnings': total_paid_extra
    }
    
    return render(request, 'agent/dashboard.html', context)

# Add Customer: Agent submits customer details and documents
def add_customer(request):
    agent_id = request.session.get('agent_id')
    if not agent_id:
        return redirect('agent_login')
    agent = get_object_or_404(Agent, id=agent_id)
    
    if request.method == 'POST':
        try:
            Customer.objects.create(
                agent=agent,
                customer_name=request.POST.get('customer_name'),
                aadhaar_card=request.FILES.get('aadhaar_card'),
                pan_card=request.FILES.get('pan_card'),
                electricity_bill=request.FILES.get('electricity_bill'),
                mobile_number=request.POST.get('mobile_number'),
                bank_document=request.FILES.get('bank_document'),
                roof_photo=request.FILES.get('roof_photo'),
                meter_photo=request.FILES.get('meter_photo'),
                passport_photo=request.FILES.get('passport_photo'),
                ownership_proof=request.FILES.get('ownership_proof'),
                vendor_quotation=request.FILES.get('vendor_quotation'),
                address=request.POST.get('address')
            )
            messages.success(request, "Customer submitted successfully!")
            return redirect('agent_customer_list')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            
    return render(request, 'agent/add_customer.html', {'agent': agent})

# Agent Customer List: Shows all customers submitted by the logged-in agent
def agent_customer_list(request):
    agent_id = request.session.get('agent_id')
    if not agent_id:
        return redirect('agent_login')
    agent = get_object_or_404(Agent, id=agent_id)
    
    status_filter = request.GET.get('status')
    customers = Customer.objects.filter(agent=agent).order_by('-created_at')
    
    if status_filter:
        customers = customers.filter(status=status_filter)
        
    return render(request, 'agent/customer_list.html', {
        'customers': customers, 
        'agent': agent,
        'status_filter': status_filter
    })

# Agent Commission View: Agent sees their earnings and payment history
def agent_commission_view(request):
    agent_id = request.session.get('agent_id')
    if not agent_id:
        return redirect('agent_login')
    agent = get_object_or_404(Agent, id=agent_id)
    
    # Regular stats (Approved + Confirmed counts for base commission)
    approved_count = Customer.objects.filter(agent=agent, status__in=['Approved', 'Confirmed']).count()
    confirmed_count = Customer.objects.filter(agent=agent, status='Confirmed').count()
    
    total_earnings = approved_count * 20
    total_paid_regular = Payment.objects.filter(agent=agent, payment_type='Regular').aggregate(Sum('amount'))['amount__sum'] or 0
    total_paid_extra = Payment.objects.filter(agent=agent, payment_type='Extra').aggregate(Sum('amount'))['amount__sum'] or 0
    
    total_paid = total_paid_regular + total_paid_extra
    balance = total_earnings - float(total_paid_regular)
    
    # Get all payment history (Regular + Extra)
    payments = Payment.objects.filter(agent=agent).order_by('-date')
    
    return render(request, 'agent/agent_commission_list.html', {
        'agent': agent,
        'approved_count': approved_count,
        'confirmed_count': confirmed_count,
        'total_earnings': total_earnings,
        'total_paid': total_paid,
        'total_paid_regular': total_paid_regular,
        'total_paid_extra': total_paid_extra,
        'balance': balance,
        'payments': payments
    })

# Agent Extra Commission View
def agent_extra_commission_view(request):
    agent_id = request.session.get('agent_id')
    if not agent_id:
        return redirect('agent_login')
    agent = get_object_or_404(Agent, id=agent_id)
    
    # Extra stats
    confirmed_count = Customer.objects.filter(agent=agent, status='Confirmed').count()
    total_paid_extra = Payment.objects.filter(agent=agent, payment_type='Extra').aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Get extra payment history
    payments = Payment.objects.filter(agent=agent, payment_type='Extra').order_by('-date')
    
    return render(request, 'agent/extra_commission_list.html', {
        'agent': agent,
        'confirmed_count': confirmed_count,
        'total_paid_extra': total_paid_extra,
        'payments': payments
    })

# ==========================================
# ADMIN CUSTOMER MANAGEMENT
# ==========================================

# Work for Vendor: List of confirmed customers to be assigned to vendors
def vendor_work_list(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    # Get only unassigned customers
    customers = Customer.objects.filter(vendor__isnull=True).order_by('-created_at')
    vendors = Vendor.objects.filter(is_active=True)
    
    return render(request, 'admin/vendor_work_list.html', {
        'customers': customers,
        'vendors': vendors
    })

# Assigned Work List: View all assigned work with status
def assigned_work_list(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    # Get all vendors for filter dropdown
    vendors = Vendor.objects.filter(is_active=True)
    
    # Get filter parameters from request
    vendor_filter = request.GET.get('vendor')
    status_filter = request.GET.get('status')
    
    # Build queryset with filters
    assigned_customers = Customer.objects.filter(vendor__isnull=False).order_by('-assigned_to_vendor_at')
    
    if vendor_filter:
        assigned_customers = assigned_customers.filter(vendor__id=vendor_filter)
    if status_filter:
        assigned_customers = assigned_customers.filter(status=status_filter)
    
    # Pagination: 10 items per page
    paginator = Paginator(assigned_customers, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Preserve filter parameters in pagination links
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    filter_querystring = query_params.urlencode()
    
    return render(request, 'admin/assigned_work_list.html', {
        'page_obj': page_obj,
        'vendors': vendors,
        'selected_vendor': vendor_filter,
        'selected_status': status_filter,
        'filter_querystring': filter_querystring
    })

# Assign Customer to Vendor
def assign_vendor(request, cust_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    if request.method == 'POST':
        customer = get_object_or_404(Customer, id=cust_id)
        
        # Check if already assigned to a vendor
        if customer.vendor:
            messages.error(request, f"Customer {customer.customer_name} is already assigned to {customer.vendor.company_name}! Re-assignment is not allowed.")
            return redirect('vendor_work_list')
        
        vendor_id = request.POST.get('vendor_id')
        remark = request.POST.get('vendor_remark')
        
        if vendor_id:
            vendor = get_object_or_404(Vendor, id=vendor_id)
            customer.vendor = vendor
            customer.vendor_remark = remark
            customer.assigned_to_vendor_at = timezone.now()
            # Reset vendor status fields to default
            customer.vendor_status = 'Pending'
            customer.vendor_status_remark = None
            customer.vendor_status_updated_at = None
            customer.save()
            messages.success(request, f"Customer {customer.customer_name} assigned to {vendor.company_name}")
        else:
            messages.error(request, "Please select a vendor")
            
    return redirect('vendor_work_list')

# Admin Customer Summary: Agent-wise summary table
def admin_customer_summary(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    agents = Agent.objects.annotate(
        total_cust=Count('customers'),
        approved_cust=Count('customers', filter=Q(customers__status='Approved')),
        confirmed_cust=Count('customers', filter=Q(customers__status='Confirmed')),
        rejected_cust=Count('customers', filter=Q(customers__status='Rejected'))
    ).order_by('-total_cust')
    
    return render(request, 'admin/admin_customer_list.html', {'agents': agents})

# Admin Agent Customers: Detailed list of customers for a specific agent
def admin_agent_customers(request, agent_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    agent = get_object_or_404(Agent, id=agent_id)
    customers = Customer.objects.filter(agent=agent).order_by('-created_at')
    return render(request, 'admin/admin_agent_customers.html', {'agent': agent, 'customers': customers})

# Customer Details: Admin views all uploaded documents
def customer_details(request, cust_id):
    customer = get_object_or_404(Customer, id=cust_id)
    
    # Check if user is admin
    if request.user.is_authenticated and request.user.is_staff:
        return render(request, 'admin/customer_details.html', {'customer': customer})
    
    # Check if user is agent and owns this customer
    agent_id = request.session.get('agent_id')
    if agent_id:
        try:
            agent = Agent.objects.get(id=agent_id)
            if customer.agent == agent:
                return render(request, 'admin/customer_details.html', {'customer': customer})
        except Agent.DoesNotExist:
            pass
    
    # Check if user is vendor and this customer is assigned to them
    vendor_id = request.session.get('vendor_id')
    if vendor_id:
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            if customer.vendor == vendor:
                return render(request, 'admin/customer_details.html', {'customer': customer})
        except Vendor.DoesNotExist:
            pass
    
    # If none of the above, redirect to login
    messages.error(request, "You are not authorized to view this customer!")
    if request.user.is_staff:
        return redirect('admin_login')
    elif agent_id:
        return redirect('agent_login')
    elif vendor_id:
        return redirect('vendor_login')
    else:
        return redirect('home')

# Download All Documents as ZIP
def download_all_documents(request, cust_id):
    customer = get_object_or_404(Customer, id=cust_id)
    authorized = False
    
    # Check if user is admin
    if request.user.is_authenticated and request.user.is_staff:
        authorized = True
    
    # Check if user is agent and owns this customer
    if not authorized:
        agent_id = request.session.get('agent_id')
        if agent_id:
            try:
                agent = Agent.objects.get(id=agent_id)
                if customer.agent == agent:
                    authorized = True
            except Agent.DoesNotExist:
                pass
    
    # Check if user is vendor and this customer is assigned to them
    if not authorized:
        vendor_id = request.session.get('vendor_id')
        if vendor_id:
            try:
                vendor = Vendor.objects.get(id=vendor_id)
                if customer.vendor == vendor:
                    authorized = True
            except Vendor.DoesNotExist:
                pass
    
    if not authorized:
        messages.error(request, "You are not authorized to download these documents!")
        if request.user.is_staff:
            return redirect('admin_login')
        elif agent_id:
            return redirect('agent_login')
        elif vendor_id:
            return redirect('vendor_login')
        else:
            return redirect('home')
    
    # Create an in-memory ZIP file
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zip_file:
        # List of document fields
        documents = {
            'Aadhaar_Card': customer.aadhaar_card,
            'PAN_Card': customer.pan_card,
            'Electricity_Bill': customer.electricity_bill,
            'Bank_Document': customer.bank_document,
            'Roof_Photo': customer.roof_photo,
            'Meter_Photo': customer.meter_photo,
            'Passport_Photo': customer.passport_photo,
            'Ownership_Proof': customer.ownership_proof,
            'Vendor_Quotation': customer.vendor_quotation,
        }
        
        for name, field in documents.items():
            if field:
                # Get the file path and extension
                file_path = field.path
                ext = file_path.split('.')[-1]
                # Add to ZIP with a clean name
                zip_file.write(file_path, f"{name}.{ext}")
                
    # Prepare the response
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="Documents_{customer.customer_name.replace(" ", "_")}.zip"'
    return response

# Download All Documents as ZIP (Vendor)
def vendor_download_all_documents(request, cust_id):
    vendor_id = request.session.get('vendor_id')
    if not vendor_id:
        return redirect('vendor_login')
    
    vendor = get_object_or_404(Vendor, id=vendor_id)
    customer = get_object_or_404(Customer, id=cust_id, vendor=vendor)
    
    # Create an in-memory ZIP file
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zip_file:
        # List of document fields
        documents = {
            'Aadhaar_Card': customer.aadhaar_card,
            'PAN_Card': customer.pan_card,
            'Electricity_Bill': customer.electricity_bill,
            'Bank_Document': customer.bank_document,
            'Roof_Photo': customer.roof_photo,
            'Meter_Photo': customer.meter_photo,
            'Passport_Photo': customer.passport_photo,
            'Ownership_Proof': customer.ownership_proof,
            'Vendor_Quotation': customer.vendor_quotation,
        }
        
        for name, field in documents.items():
            if field:
                # Get the file path and extension
                file_path = field.path
                ext = file_path.split('.')[-1]
                # Add to ZIP with a clean name
                zip_file.write(file_path, f"{name}.{ext}")
                
    # Prepare the response
    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="Documents_{customer.customer_name.replace(" ", "_")}.zip"'
    return response

# ==========================================
# VENDOR DOCUMENT PAYMENT VIEWS
# ==========================================

# Vendor Document Payment List: Shows all customers where vendor has completed, and payment status
def vendor_document_payment(request):
    vendor_id = request.session.get('vendor_id')
    if not vendor_id:
        return redirect('vendor_login')
    vendor = get_object_or_404(Vendor, id=vendor_id)
    
    # Customers assigned to vendor, where vendor_status is Complete
    customers = Customer.objects.filter(vendor=vendor, vendor_status='Complete').order_by('-vendor_status_updated_at')
    completed_count = customers.count()
    
    # Payment history
    payments = VendorDocumentPayment.objects.filter(vendor=vendor).order_by('-date')
    total_paid = payments.aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Calculate pending payments
    paid_customers = customers.filter(vendor_doc_payment_done=True)
    pending_customers = customers.filter(vendor_doc_payment_done=False)
    pending_count = pending_customers.count()
    pending_amount = pending_count * 100
    
    context = {
        'vendor': vendor,
        'customers': customers,
        'payments': payments,
        'approved_count': completed_count,
        'total_paid': total_paid,
        'pending_count': pending_count,
        'pending_amount': pending_amount
    }
    
    return render(request, 'vendor/document_payment_list.html', context)

# Vendor Document Payment Form: For a specific customer
def vendor_document_payment_form(request, cust_id):
    vendor_id = request.session.get('vendor_id')
    if not vendor_id:
        return redirect('vendor_login')
    vendor = get_object_or_404(Vendor, id=vendor_id)
    customer = get_object_or_404(Customer, id=cust_id, vendor=vendor)
    
    if customer.vendor_status != 'Complete':
        messages.warning(request, "This customer is not completed yet!")
        return redirect('vendor_document_payment')
    
    if customer.vendor_doc_payment_done:
        messages.warning(request, "Payment already done for this customer!")
        return redirect('vendor_document_payment')
    
    if request.method == 'POST':
        method = request.POST.get('payment_method')
        utr_number = request.POST.get('utr_number', '')
        remark = request.POST.get('remark', '')
        
        # Create payment
        VendorDocumentPayment.objects.create(
            vendor=vendor,
            customer=customer,
            amount=100.00,
            method=method,
            utr_number=utr_number,
            remark=remark
        )
        
        # Mark payment done
        customer.vendor_doc_payment_done = True
        customer.save()
        
        messages.success(request, "Payment recorded successfully!")
        return redirect('vendor_document_payment')
    
    return render(request, 'vendor/document_payment_form.html', {
        'vendor': vendor,
        'customer': customer
    })

# Update Customer Status: Admin Approves, Confirms, or Rejects
def update_status(request, cust_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    customer = get_object_or_404(Customer, id=cust_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        remark = request.POST.get('remark', '')
        
        customer.status = new_status
        if new_status == 'Rejected':
            customer.remark = remark
        else:
            customer.remark = "" # Clear remark if approved/confirmed
        
        # Also update vendor_status to match admin status for consistency
        if new_status == 'Pending':
            customer.vendor_status = 'Pending'
        elif new_status == 'Approved':
            customer.vendor_status = 'Approve'
        elif new_status == 'Confirmed':
            customer.vendor_status = 'Complete'
        elif new_status == 'Rejected':
            customer.vendor_status = 'Hold'
            
        # Set who updated the status
        customer.status_updated_by_name = "Admin"
        customer.status_updated_by_role = "Admin"
            
        customer.save()
        
        # Save to status history
        from app.models import CustomerStatusHistory
        CustomerStatusHistory.objects.create(
            customer=customer,
            status=new_status,
            changed_by_name="Admin",
            changed_by_role="Admin",
            remark=remark
        )
        
        messages.success(request, f"Customer status updated to {new_status}!")
        
    return redirect('admin_agent_customers', agent_id=customer.agent.id)

# ==========================================
# LOGOUT SYSTEM
# ==========================================

# Logout View: Clears both Admin and Agent sessions
def logout_view(request):
    # Clear custom agent session
    if 'agent_id' in request.session:
        del request.session['agent_id']
        del request.session['agent_name']
    # Clear Django user session
    logout(request)
    messages.success(request, "Logged out successfully!")
    return redirect('home')

# ==========================================
# ADMIN - VENDOR DOCUMENT PAYMENTS
# ==========================================
def admin_vendor_document_payments(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    # Get all vendors with data
    vendors_data = []
    vendors = Vendor.objects.all().order_by('-created_at')
    
    for vendor in vendors:
        total_customers = Customer.objects.filter(vendor=vendor).count()
        completed_customers = Customer.objects.filter(vendor=vendor, vendor_status='Complete').count()
        total_payments = VendorDocumentPayment.objects.filter(vendor=vendor).aggregate(Sum('amount'))['amount__sum'] or 0
        payment_count = VendorDocumentPayment.objects.filter(vendor=vendor).count()
        pending_amount = (completed_customers * 100) - total_payments
        
        vendors_data.append({
            'vendor': vendor,
            'total_customers': total_customers,
            'completed_customers': completed_customers,
            'total_payments': total_payments,
            'payment_count': payment_count,
            'pending_amount': pending_amount
        })
    
    context = {
        'vendors_data': vendors_data
    }
    
    return render(request, 'admin/vendor_document_payments.html', context)

def admin_vendor_document_payment_details(request, vendor_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    vendor = get_object_or_404(Vendor, id=vendor_id)
    payments = VendorDocumentPayment.objects.filter(vendor=vendor).order_by('-date')
    
    context = {
        'vendor': vendor,
        'payments': payments
    }
    
    return render(request, 'admin/vendor_document_payment_details.html', context)

# ==========================================
# CHAT SYSTEM
# ==========================================

# Admin Chat List: Show all vendors in a list with search
def admin_chat_list(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    search_query = request.GET.get('search', '')
    
    # Get all vendors with last message and unread count
    vendors = Vendor.objects.filter(is_active=True).annotate(
        last_message_time=Max('chat_messages__created_at'),
        unread_count=Count('chat_messages', filter=Q(chat_messages__sender='Vendor', chat_messages__is_read=False))
    ).order_by('-last_message_time', '-created_at')
    
    if search_query:
        vendors = vendors.filter(
            Q(name__icontains=search_query) | Q(company_name__icontains=search_query)
        )
    
    # Get unread messages count for chat notifications
    unread_messages_count = ChatMessage.objects.filter(sender='Vendor', is_read=False).count()
    
    return render(request, 'admin/chat_list.html', {
        'vendors': vendors, 
        'unread_messages_count': unread_messages_count,
        'search_query': search_query
    })

# Admin Chat: Admin chats with a specific vendor
def admin_chat(request, vendor_id):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect('admin_login')
    
    vendor = get_object_or_404(Vendor, id=vendor_id)
    messages = ChatMessage.objects.filter(vendor=vendor).order_by('created_at')
    
    # Mark all vendor messages as read
    messages.filter(sender='Vendor', is_read=False).update(is_read=True)
    
    # Get all vendors with last message and unread count for sidebar
    vendors = Vendor.objects.filter(is_active=True).annotate(
        last_message_time=Max('chat_messages__created_at'),
        unread_count=Count('chat_messages', filter=Q(chat_messages__sender='Vendor', chat_messages__is_read=False))
    ).order_by('-last_message_time', '-created_at')
    
    # Get unread messages count for chat notifications
    unread_messages_count = ChatMessage.objects.filter(sender='Vendor', is_read=False).count()
    
    context = {
        'vendor': vendor,
        'messages': messages,
        'vendors': vendors,
        'unread_messages_count': unread_messages_count
    }
    
    return render(request, 'admin/chat.html', context)

# Vendor Chat: Vendor chats with admin
def vendor_chat(request):
    vendor_id = request.session.get('vendor_id')
    if not vendor_id:
        return redirect('vendor_login')
    
    vendor = get_object_or_404(Vendor, id=vendor_id)
    
    # Update last seen
    vendor.last_seen = timezone.now()
    vendor.save()
    
    messages = ChatMessage.objects.filter(vendor=vendor).order_by('created_at')
    
    # Mark all admin messages as read
    messages.filter(sender='Admin', is_read=False).update(is_read=True)
    
    context = {
        'vendor': vendor,
        'messages': messages
    }
    
    return render(request, 'vendor/chat.html', context)

# Send Chat Message (common for admin and vendor)
def send_chat_message(request):
    if request.method == 'POST':
        # Check if admin
        if request.user.is_authenticated and request.user.is_staff:
            vendor_id = request.POST.get('vendor_id')
            vendor = get_object_or_404(Vendor, id=vendor_id)
            sender = 'Admin'
        # Check if vendor
        elif request.session.get('vendor_id'):
            vendor_id = request.session.get('vendor_id')
            vendor = get_object_or_404(Vendor, id=vendor_id)
            sender = 'Vendor'
            # Update last seen
            vendor.last_seen = timezone.now()
            vendor.save()
        else:
            return JsonResponse({'success': False, 'error': 'Not authenticated'})
        
        message_text = request.POST.get('message', '').strip()
        image = request.FILES.get('image')
        
        if message_text or image:
            chat_message = ChatMessage.objects.create(
                vendor=vendor,
                sender=sender,
                message=message_text if message_text else None,
                image=image if image else None
            )
            
            # Prepare response data
            response_data = {
                'success': True,
                'message': chat_message.message,
                'image_url': chat_message.image.url if chat_message.image else None,
                'sender': chat_message.sender,
                'created_at': chat_message.created_at.strftime('%d %b %Y %H:%M')
            }
            
            return JsonResponse(response_data)
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})
