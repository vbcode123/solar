from django.urls import path
from . import views

urlpatterns = [
    # Main Landing Page
    path('', views.home, name='home'),

    # Admin Authentication & Dashboard
    path('admin-login/', views.admin_login, name='admin_login'), # Admin Login Page
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'), # Admin Dashboard Stats
    path('admin-all-customers/', views.all_customers_list, name='all_customers_list'), # All Customers Filterable List (Admin)

    # Agent Management (Admin Only)
    path('add-agent/', views.add_agent, name='add_agent'), # Form to add new agent
    path('agent-list/', views.agent_list, name='agent_list'), # List of all agents
    path('view-agent/<int:id>/', views.view_agent, name='view_agent'), # View full agent profile
    path('toggle-access/<int:id>/', views.toggle_access, name='toggle_access'), # Enable/Disable agent login
    path('edit-agent/<int:id>/', views.edit_agent, name='edit_agent'), # Edit agent details
    path('delete-agent/<int:id>/', views.delete_agent, name='delete_agent'), # Delete agent from system

    # Vendor Management (Admin Only)
    path('add-vendor/', views.add_vendor, name='add_vendor'), # Form to add new vendor
    path('vendor-list/', views.vendor_list, name='vendor_list'), # List of all vendors
    path('view-vendor/<int:id>/', views.view_vendor, name='view_vendor'), # View full vendor profile
    path('edit-vendor/<int:id>/', views.edit_vendor, name='edit_vendor'), # Edit vendor details
    path('delete-vendor/<int:id>/', views.delete_vendor, name='delete_vendor'), # Delete vendor

    # Agent Authentication & Dashboard
    path('agent-login/', views.agent_login, name='agent_login'), # Agent Login Page
    path('agent-dashboard/', views.agent_dashboard, name='agent_dashboard'), # Agent Dashboard Stats

    # Vendor Authentication & Dashboard
    path('vendor-login/', views.vendor_login, name='vendor_login'), # Vendor Login Page
    path('vendor-dashboard/', views.vendor_dashboard, name='vendor_dashboard'), # Vendor Dashboard
    path('vendor-logout/', views.vendor_logout, name='vendor_logout'), # Vendor Logout
    
    # Vendor Job Management (Vendor Side)
    path('vendor-installation-jobs/', views.vendor_installation_jobs, name='vendor_installation_jobs'),
    path('vendor-job-details/<int:cust_id>/', views.vendor_job_details, name='vendor_job_details'),
    path('update-vendor-status/<int:cust_id>/', views.update_vendor_status, name='update_vendor_status'),
    path('vendor-download-all-documents/<int:cust_id>/', views.vendor_download_all_documents, name='vendor_download_all_documents'),

    # Customer Management (Agent Side)
    path('add-customer/', views.add_customer, name='add_customer'), # Agent submits new customer application
    path('agent-customer-list/', views.agent_customer_list, name='agent_customer_list'), # Agent's own customer list

    # Earnings & Commissions (Agent Side)
    path('agent-commission/', views.agent_commission_view, name='agent_commission'), # Agent's regular earnings list
    path('agent-extra-commission/', views.agent_extra_commission_view, name='agent_extra_commission'), # Agent's extra earnings list

    # Customer Management (Admin Side)
    path('admin-customer-summary/', views.admin_customer_summary, name='admin_customer_summary'), # Summary of customers per agent
    path('admin-agent-customers/<int:agent_id>/', views.admin_agent_customers, name='admin_agent_customers'), # List of customers for a specific agent
    path('customer-details/<int:cust_id>/', views.customer_details, name='customer_details'), # View all docs for a customer
    path('download-documents/<int:cust_id>/', views.download_all_documents, name='download_all_documents'), # Download all docs as ZIP
    path('update-status/<int:cust_id>/', views.update_status, name='update_status'), # Admin Approves/Rejects/Confirms status
    
    # Vendor Work Assignment (Admin Side)
    path('vendor-work-list/', views.vendor_work_list, name='vendor_work_list'),
    path('assigned-work-list/', views.assigned_work_list, name='assigned_work_list'),
    path('assign-vendor/<int:cust_id>/', views.assign_vendor, name='assign_vendor'),
    
    # Chat System (Admin-Vendor)
    path('admin-chat/', views.admin_chat_list, name='admin_chat_list'),
    path('admin-chat/<int:vendor_id>/', views.admin_chat, name='admin_chat'),
    path('vendor-chat/', views.vendor_chat, name='vendor_chat'),
    path('send-chat-message/', views.send_chat_message, name='send_chat_message'),
    
    # Agent Chat System (Admin-Agent)
    path('admin-agent-chat/', views.admin_agent_chat_list, name='admin_agent_chat_list'),
    path('admin-agent-chat/<int:agent_id>/', views.admin_agent_chat, name='admin_agent_chat'),
    path('agent-chat/', views.agent_chat, name='agent_chat'),
    path('send-agent-chat-message/', views.send_agent_chat_message, name='send_agent_chat_message'),

    # Payout Management (Admin Side)
    path('agent-commissions/', views.agent_commissions, name='agent_commissions'), # Admin view of all agent regular earnings
    path('agent-payment/<int:agent_id>/', views.agent_payment, name='agent_payment'), # Admin records payment for an agent
    path('extra-commissions/', views.extra_commissions, name='extra_commissions'), # Admin view of all agent extra earnings
    path('extra-payment/<int:agent_id>/', views.extra_payment, name='extra_payment'), # Admin records extra payment for an agent
    path('customer-extra-payment/<int:customer_id>/', views.customer_extra_payment, name='customer_extra_payment'), # Admin records extra payment for individual customer

    # Vendor Document Payment (Vendor Side)
    path('vendor-document-payment/', views.vendor_document_payment, name='vendor_document_payment'),
    path('vendor-document-payment/<int:cust_id>/', views.vendor_document_payment_form, name='vendor_document_payment_form'),
    
    # Vendor Document Payment (Admin Side)
    path('vendor-document-payments/', views.admin_vendor_document_payments, name='admin_vendor_document_payments'),
    path('vendor-document-payments/<int:vendor_id>/', views.admin_vendor_document_payment_details, name='admin_vendor_document_payment_details'),

    # Logout System
    path('logout/', views.logout_view, name='logout'), # Logout for both Admin & Agent
]
