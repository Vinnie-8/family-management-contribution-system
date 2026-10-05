#Importing all models here registers the tables on Base.metadata in one place 

from app.models.family import Family                         
from app.models.role import Role                               
from app.models.member import Member                           
from app.models.member_role import MemberRole                      
from app.models.audit_log import AuditLog                      
from app.models.household import HouseHold                     
from app.models.guardian_link import GuardianLink               
from app.models.financial_year import FinancialYear             
from app.models.campaign import Campaign                      
from app.models.contribution_rule import ContributionRule       
from app.models.event import Event                            
from app.models.campaign_event import CampaignEvent             
from app.models.budget import Budget                           
from app.models.pledge import Pledge                          
from app.models.pledge_installment import PledgeInstallment     
from app.models.standing_fund import StandingFund               
from app.models.payment import Payment                         
from app.models.fine import Fine                               
from app.models.expense import Expense                         
from app.models.dispute import Dispute                         
from app.models.meeting import Meeting                         
from app.models.attendance import Attendance                   
from app.models.minutes_record import MinutesRecord             
from app.models.handover_record import HandoverRecord           
from app.models.notification import Notification               
from app.models.document import Document   