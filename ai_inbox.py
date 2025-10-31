import os
import json
import time
import logging
import random
import re
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from dataclasses import asdict
import hashlib
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Import your data models
from models import Contact, ConversationMetrics, ConversationStage, MessageIntent

logger = logging.getLogger(__name__)

class EnhancedAIInbox:
    """LinkedHelper 2 style AI inbox with advanced features"""
    
    def __init__(self, gemini_model=None):
        self.model = gemini_model
        self.conversations_db = "conversations_db.json"
        self.leads_db = "leads_db.json"
        self.templates_db = "message_templates.json"
        self.settings_file = "inbox_settings.json"
        
        # Load or create databases
        self.conversations = self.load_json_db(self.conversations_db, {})
        self.leads = self.load_json_db(self.leads_db, {})
        self.templates = self.load_json_db(self.templates_db, self.get_default_templates())
        self.settings = self.load_json_db(self.settings_file, self.get_default_settings())
        
        # Response templates by stage and intent
        self.response_strategies = self.build_response_strategies()
        self.active_inbox_sessions = {}
    
    def load_json_db(self, filename: str, default_data: Any) -> Any:
        """Load JSON database with error handling"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load {filename}: {e}")
        return default_data
    
    def save_json_db(self, filename: str, data: Any):
        """Save JSON database with error handling"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Could not save {filename}: {e}")
        
    def navigate_to_messaging_safe(self, driver, retries=3):
        """Navigate to LinkedIn messaging with better recovery"""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        logger.info("📨 Navigating to LinkedIn messaging...")
        
        for attempt in range(1, retries + 1):
            try:
                current_url = driver.current_url
                
                # Only navigate if not already on messaging page
                if "/messaging" not in current_url:
                    driver.get("https://www.linkedin.com/messaging")
                
                # Wait for any of the conversation list elements
                WebDriverWait(driver, 20).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "ul.msg-conversations-container__conversations-list")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.msg-threads")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".msg-conversation-listitem")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "aside.msg-s-message-list-container"))
                    )
                )
                
                # Wait for conversations to be clickable
                time.sleep(2)
                
                logger.info("✅ Successfully loaded messaging page.")
                return True
                
            except Exception as e:
                logger.warning(f"⚠️ Attempt {attempt}/{retries} failed to load messaging: {e}")
                if attempt < retries:
                    driver.refresh()
                    time.sleep(random.uniform(3, 6))
        
        logger.error("❌ Failed to load messaging page after retries.")
        return False

    
    def get_default_templates(self) -> Dict[str, Dict[str, str]]:
        """Default message templates"""
        return {
            "positive_followup": {
                "template": "Hi {name}, thanks for your positive response! I'd love to learn more about {company}'s current challenges with {industry_topic}. Would you be open to a brief 15-minute call this week?",
                "triggers": ["interested", "sounds good", "tell me more", "yes"]
            },
            "objection_handling": {
                "template": "I understand {name}. Many {title}s at companies like {company} have similar concerns. What if I could show you how we've helped similar companies overcome this exact challenge in just 15 minutes?",
                "triggers": ["not interested", "no budget", "no time", "already have"]
            },
            "demo_request": {
                "template": "Hi {name}, I'd be happy to show you exactly how this works for {company}. I have a few slots available this week - would Tuesday or Wednesday work better for a quick 20-minute demo?",
                "triggers": ["demo", "show me", "how does it work", "see it in action"]
            },
            "pricing_inquiry": {
                "template": "Hi {name}, great question! Our pricing depends on {company}'s specific needs. I'd love to understand your requirements better so I can provide accurate pricing. Could we schedule a brief call?",
                "triggers": ["price", "cost", "how much", "pricing", "budget"]
            },
            "referral_request": {
                "template": "Thanks {name}! I appreciate that. Do you know anyone at {company} or in your network who might benefit from this? I'd be happy to provide value to your connections as well.",
                "triggers": ["not the right person", "talk to", "someone else handles"]
            }
        }
    
    def get_default_settings(self) -> Dict[str, Any]:
        """Default inbox processing settings - IMPROVED VERSION"""
        return {
            "auto_reply_enabled": True,
            "max_daily_replies": 50,
            "min_lead_score": 25,  # LOWERED from 30 to 25
            "response_delay_min": 5,
            "response_delay_max": 60,
            "working_hours": {"start": 9, "end": 17},
            "blacklist_keywords": ["spam", "unsubscribe", "remove", "not interested"],
            "priority_keywords": ["urgent", "asap", "important", "meeting", "demo", "call"],
            "qualification_questions": [
                "What's your current process for {topic}?",
                "What challenges are you facing with {topic}?",
                "What's your timeline for making a decision?",
                "Who else would be involved in this decision?"
            ]
        }
    
    def build_response_strategies(self) -> Dict[str, Dict[str, str]]:
        """Build response strategies matrix"""
        return {
            "cold_outreach": {
                "positive_response": "followup_interest",
                "question": "answer_and_qualify", 
                "request_info": "provide_info_and_demo",
                "objection": "handle_objection",
                "not_interested": "soft_nurture"
            },
            "initial_response": {
                "positive_response": "qualify_needs",
                "question": "answer_and_schedule",
                "request_info": "send_resources",
                "schedule_meeting": "propose_times",
                "price_inquiry": "qualify_budget"
            },
            "interest_shown": {
                "positive_response": "schedule_demo",
                "question": "detailed_answer", 
                "schedule_meeting": "confirm_meeting",
                "price_inquiry": "custom_proposal",
                "objection": "overcome_objection"
            },
            "qualification": {
                "positive_response": "move_to_demo",
                "question": "qualify_further",
                "schedule_meeting": "demo_meeting",
                "objection": "address_concerns",
                "request_info": "detailed_proposal"
            }
        }
    
    def analyze_message_intent(self, message: str) -> MessageIntent:
        """Analyze message intent using AI and keywords"""
        message_lower = message.lower()
        
        # Keyword-based classification (fast)
        intent_keywords = {
            MessageIntent.POSITIVE_RESPONSE: ["yes", "interested", "sounds good", "tell me more", "great", "perfect"],
            MessageIntent.NEGATIVE_RESPONSE: ["no", "not interested", "no thanks", "remove", "unsubscribe"],
            MessageIntent.QUESTION: ["?", "how", "what", "when", "where", "why", "can you"],
            MessageIntent.REQUEST_INFO: ["send", "share", "information", "details", "more info", "brochure"],
            MessageIntent.SCHEDULE_MEETING: ["meeting", "call", "schedule", "calendar", "available", "free time"],
            MessageIntent.PRICE_INQUIRY: ["price", "cost", "how much", "pricing", "budget", "fees"],
            MessageIntent.OBJECTION: ["but", "however", "already have", "too expensive", "no budget"],
            MessageIntent.REFERRAL: ["not the right person", "speak to", "contact", "someone else"],
            MessageIntent.OUT_OF_OFFICE: ["out of office", "vacation", "away", "back on"],
            MessageIntent.SPAM: ["viagra", "casino", "lottery", "prince"]
        }
        
        for intent, keywords in intent_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                return intent
        
        # AI-based classification for complex cases
        if self.model:
            try:
                ai_intent = self.classify_message_with_ai(message)
                if ai_intent:
                    return ai_intent
            except Exception as e:
                logger.debug(f"AI intent classification failed: {e}")
        
        return MessageIntent.POSITIVE_RESPONSE  # Default
    
    def classify_message_with_ai(self, message: str) -> Optional[MessageIntent]:
        """Use AI to classify message intent"""
        prompt = f"""Analyze this LinkedIn message and classify its intent.

Message: "{message}"

Classify into ONE of these categories:
- positive_response: Shows interest, agreement, or positive engagement
- negative_response: Clearly not interested, wants to unsubscribe
- question: Asking questions about the product/service
- request_info: Wants more information, resources, or details
- schedule_meeting: Wants to schedule a call, meeting, or demo
- price_inquiry: Asking about pricing, costs, or budget
- objection: Has concerns, objections, or challenges
- referral: Suggesting to talk to someone else
- out_of_office: Auto-reply indicating they're away
- spam: Spam or irrelevant message

Reply with only the category name."""

        try:
            response = self.model.generate_content(prompt)
            intent_str = response.text.strip().lower()
            
            for intent in MessageIntent:
                if intent.value in intent_str:
                    return intent
                    
        except Exception as e:
            logger.error(f"AI classification error: {e}")
        
        return None
    
    def calculate_lead_score(self, contact: Contact, conversation_history: List[Dict[str, str]], 
                       metrics: ConversationMetrics) -> int:
        """Calculate lead score (0-100) - IMPROVED VERSION"""
        score = 30  # Start with base score instead of 0
        
        # Valid conversation exists bonus
        if len(conversation_history) > 0:
            score += 10
        
        # Company size indicators
        if contact.connections:
            conn_match = re.search(r'(\d+)', contact.connections)
            if conn_match:
                conn_count = int(conn_match.group(1))
                if conn_count > 500:
                    score += 15
                elif conn_count > 200:
                    score += 10
                elif conn_count > 100:
                    score += 5
        
        # Title/seniority scoring
        if contact.title:
            title_lower = contact.title.lower()
            senior_titles = ["ceo", "cto", "cfo", "vp", "vice president", "director", "head", "manager", "founder", "owner", "president"]
            if any(title in title_lower for title in senior_titles):
                score += 20
            else:
                score += 5  # Any title is better than none
        
        # Industry relevance
        if contact.industry:
            relevant_industries = ["technology", "software", "saas", "fintech", "healthcare", "consulting", "services"]
            if any(industry in contact.industry.lower() for industry in relevant_industries):
                score += 15
        
        # Conversation engagement - they initiated or responded
        if len(conversation_history) >= 1:
            score += 5
        if len(conversation_history) > 1:
            score += 10
        if len(conversation_history) > 3:
            score += 10
        
        # Response patterns - look for positive signals
        positive_indicators = ["interested", "tell me more", "sounds good", "yes", "demo", "meeting", "call", "schedule", "discuss", "learn more"]
        recent_messages = conversation_history[-3:] if len(conversation_history) >= 3 else conversation_history
        
        for msg in recent_messages:
            if msg.get('sender') != 'You':
                msg_text = msg.get('message', '').lower()
                positive_count = sum(1 for indicator in positive_indicators if indicator in msg_text)
                score += positive_count * 5
        
        # Message quality (length indicates thoughtfulness)
        if recent_messages:
            avg_length = sum(len(msg.get('message', '')) for msg in recent_messages if msg.get('sender') != 'You') / max(len([m for m in recent_messages if m.get('sender') != 'You']), 1)
            if avg_length > 100:
                score += 10
            elif avg_length > 50:
                score += 5
        
        # Question asked (shows interest)
        for msg in recent_messages:
            if msg.get('sender') != 'You' and '?' in msg.get('message', ''):
                score += 10
                break
        
        return min(score, 100)

    def should_auto_reply(self, metrics: ConversationMetrics, last_message: str) -> bool:
        """Determine if message should get auto-reply - IMPROVED VERSION"""
        settings = self.settings
        
        # Check if auto-reply is enabled
        if not settings.get('auto_reply_enabled', True):
            logger.info("Auto-reply disabled in settings")
            return False
        
        # CRITICAL: Lower the minimum lead score threshold
        min_score = settings.get('min_lead_score', 25)  # Changed from 30 to 25
        if metrics.lead_score < min_score:
            logger.info(f"Lead score {metrics.lead_score} below minimum {min_score}")
            return False
        
        # Check blacklisted keywords
        blacklist = settings.get('blacklist_keywords', [])
        if any(keyword in last_message.lower() for keyword in blacklist):
            logger.info("Message contains blacklisted keyword")
            return False
        
        # Check for spam
        if metrics.intent == MessageIntent.SPAM:
            logger.info("Message detected as spam")
            return False
        
        # Check for out of office
        if metrics.intent == MessageIntent.OUT_OF_OFFICE:
            logger.info("Out of office auto-reply detected")
            return False
        
        # Check for negative responses (don't reply to rejections)
        if metrics.intent == MessageIntent.NEGATIVE_RESPONSE:
            logger.info("Negative response detected")
            return False
        
        logger.info(f"✅ Auto-reply approved (score: {metrics.lead_score})")
        return True
    
    def determine_conversation_stage(self, conversation_history: List[Dict[str, str]], 
                                   current_intent: MessageIntent) -> ConversationStage:
        """Determine current conversation stage"""
        if not conversation_history:
            return ConversationStage.COLD_OUTREACH
        
        # Count messages from each party
        user_messages = [msg for msg in conversation_history if msg.get('sender') == 'You']
        their_messages = [msg for msg in conversation_history if msg.get('sender') != 'You']
        
        # Stage progression logic
        if len(their_messages) == 0:
            return ConversationStage.COLD_OUTREACH
        elif len(their_messages) == 1:
            return ConversationStage.INITIAL_RESPONSE
        elif current_intent in [MessageIntent.SCHEDULE_MEETING, MessageIntent.REQUEST_INFO]:
            return ConversationStage.INTEREST_SHOWN
        elif current_intent == MessageIntent.PRICE_INQUIRY:
            return ConversationStage.QUALIFICATION
        elif "demo" in conversation_history[-1].get('message', '').lower():
            return ConversationStage.DEMO_SCHEDULED
        elif len(their_messages) > 3:
            return ConversationStage.QUALIFICATION
        else:
            return ConversationStage.INITIAL_RESPONSE
    
    def generate_smart_response(self, contact: Contact, conversation_history: List[Dict[str, str]], 
                              metrics: ConversationMetrics) -> str:
        """Generate intelligent response based on context"""
        if not conversation_history:
            return "Thank you for connecting! I'll be in touch soon."
        
        last_message = conversation_history[-1].get('message', '')
        stage = metrics.stage.value
        intent = metrics.intent.value
        
        # Get response strategy
        strategy = self.response_strategies.get(stage, {}).get(intent, "general_response")
        
        # Use AI for personalized response
        if self.model:
            try:
                return self.generate_ai_response(contact, conversation_history, metrics, strategy)
            except Exception as e:
                logger.error(f"AI response generation failed: {e}")
        
        # Fallback to template-based response
        return self.generate_template_response(contact, last_message, strategy)
    
    def generate_ai_response(self, contact: Contact, conversation_history: List[Dict[str, str]], 
                           metrics: ConversationMetrics, strategy: str) -> str:
        """Generate AI response with full context"""
        
        # Format conversation history
        formatted_history = "\n".join([
            f"{msg['sender']}: {msg['message']}" for msg in conversation_history[-5:]
        ])
        
        prompt = f"""You are a professional LinkedIn sales assistant. Generate a personalized response based on the context below.

CONTACT INFORMATION:
- Name: {contact.name}
- Company: {contact.company}
- Title: {contact.title}
- Industry: {contact.industry}

CONVERSATION CONTEXT:
- Stage: {metrics.stage.value}
- Intent: {metrics.intent.value}
- Lead Score: {metrics.lead_score}/100

RECENT MESSAGES:
{formatted_history}

RESPONSE STRATEGY: {strategy}

GUIDELINES:
1. Be professional yet personable
2. Address their specific message/question
3. Match their communication style and tone
4. Keep it concise (2-3 sentences max)
5. Include a soft call-to-action when appropriate
6. Use their name naturally
7. Reference their company/industry when relevant

Generate a response:"""

        try:
            response = self.model.generate_content(prompt)
            ai_message = response.text.strip()
            
            # Clean up response
            ai_message = re.sub(r'^(Response:|Reply:)\s*', '', ai_message, flags=re.IGNORECASE)
            ai_message = ai_message.strip('"\'')
            
            # Ensure reasonable length
            if len(ai_message) > 300:
                ai_message = ai_message[:297] + "..."
            
            return ai_message
            
        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            return self.generate_template_response(contact, conversation_history[-1].get('message', ''), strategy)
    
    def generate_template_response(self, contact: Contact, last_message: str, strategy: str) -> str:
        """Generate template-based response"""
        # Find matching template
        for template_name, template_data in self.templates.items():
            triggers = template_data.get('triggers', [])
            if any(trigger in last_message.lower() for trigger in triggers):
                template = template_data['template']
                return template.format(
                    name=contact.name.split()[0] if contact.name else "there",
                    company=contact.company or "your company",
                    title=contact.title or "professional",
                    industry_topic="your industry"
                )
        
        # Default response
        name = contact.name.split()[0] if contact.name else "there"
        return f"Hi {name}, thanks for your message! I'll review this and get back to you with a thoughtful response soon."
    
    
    def save_processed_conversations(self, filename: str, conversation_ids: set):
        """Save processed conversation IDs to prevent re-processing - IMPROVED"""
        try:
            data = {
                'date': datetime.now().strftime("%Y-%m-%d"),
                'conversations': list(conversation_ids),
                'saved_at': datetime.now().isoformat()
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.info(f"💾 Saved {len(conversation_ids)} processed conversation IDs to {filename}")
        except Exception as e:
            logger.error(f"❌ Could not save processed conversations: {e}")
    
    def prioritize_conversations(self, conversations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort conversations by priority score"""
        def priority_score(conv):
            metrics = conv.get('metrics', {})
            score = 0
            
            # Lead score weight
            score += metrics.get('lead_score', 0) * 0.4
            
            # Engagement score weight  
            score += metrics.get('engagement_score', 0) * 0.3
            
            # Recency weight (more recent = higher score)
            last_interaction = metrics.get('last_interaction', '')
            if last_interaction:
                try:
                    last_time = datetime.fromisoformat(last_interaction)
                    hours_ago = (datetime.now() - last_time).total_seconds() / 3600
                    recency_score = max(0, 100 - hours_ago)  # Decreases over time
                    score += recency_score * 0.3
                except:
                    pass
            
            return score
        
        return sorted(conversations, key=priority_score, reverse=True)
    
    def extract_contact_info_enhanced(self, driver, conversation_details: Dict[str, Any]) -> Contact:
        """Extract enhanced contact information"""
        from selenium.webdriver.common.by import By
        
        contact = Contact(
            name=conversation_details.get('participant_name', 'Unknown'),
            company=conversation_details.get('participant_headline', '').split(' at ')[-1] if ' at ' in conversation_details.get('participant_headline', '') else '',
            title=conversation_details.get('participant_headline', '').split(' at ')[0] if ' at ' in conversation_details.get('participant_headline', '') else conversation_details.get('participant_headline', '')
        )
        
        # Try to extract more profile data from the current conversation view
        try:
            # Look for profile link in conversation
            profile_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/in/']")
            for link in profile_links:
                href = link.get_attribute('href')
                if '/in/' in href and 'linkedin.com' in href:
                    contact.linkedin_url = href
                    break
            
            # Extract additional info if available
            info_elements = driver.find_elements(By.CSS_SELECTOR, ".msg-thread-headline__info-text")
            for element in info_elements:
                text = element.text.strip()
                if "connections" in text.lower():
                    contact.connections = text
                elif "mutual" in text.lower():
                    contact.profile_data['mutual_connections'] = text
                    
        except Exception as e:
            logger.debug(f"Error extracting enhanced contact info: {e}")
        
        return contact
    
    def find_all_conversations(self, driver) -> List:
        """Find all conversation items with enhanced detection"""
        from selenium.webdriver.common.by import By
        
        # Wait for conversations to load
        time.sleep(2)
        
        # Multiple selector strategies for conversation items
        selectors = [
            "li.msg-conversation-listitem",
            "li.msg-conversation-card__row", 
            "li[data-view-name='conversation-list-item']",
            "div.msg-conversation-card",
            "li.msg-conversations-container__conversations-list-item",
            "div[class*='msg-conversation']",
            "li[class*='conversation-list']"
        ]
        
        all_items = []
        
        for selector in selectors:
            try:
                items = driver.find_elements(By.CSS_SELECTOR, selector)
                if items and len(items) > 0:
                    # Filter out hidden or non-visible items
                    visible_items = [item for item in items if item.is_displayed()]
                    if visible_items:
                        logger.info(f"✅ Found {len(visible_items)} visible conversations with: {selector}")
                        all_items = visible_items
                        break
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        if not all_items:
            logger.warning("❌ No conversations found with any selector")
            return []
        
        # Log detailed information about what we found
        logger.info(f"📊 Conversation breakdown:")
        unread_count = 0
        
        for idx, item in enumerate(all_items[:5]):  # Check first 5 for debugging
            try:
                classes = item.get_attribute('class') or ''
                aria_label = item.get_attribute('aria-label') or ''
                
                # Check for unread indicators
                has_unread_class = 'unread' in classes.lower()
                has_unread_label = 'unread' in aria_label.lower()
                
                try:
                    unread_badge = item.find_elements(By.CSS_SELECTOR, 
                        '.msg-conversation-card__unread-count, [data-test-id="unread-indicator"], .artdeco-entity-lockup__badge')
                    has_unread_badge = len(unread_badge) > 0
                except:
                    has_unread_badge = False
                
                is_unread = has_unread_class or has_unread_label or has_unread_badge
                
                if is_unread:
                    unread_count += 1
                
                logger.debug(f"  - Conv #{idx}: Unread={is_unread} (class={has_unread_class}, label={has_unread_label}, badge={has_unread_badge})")
                
            except Exception as e:
                logger.debug(f"  - Conv #{idx}: Could not analyze - {e}")
        
        logger.info(f"📬 Detected {unread_count} unread conversations (out of {min(5, len(all_items))} checked)")
        
        return all_items

    def save_conversation_data(self, conversation_id: str, contact: Contact, 
                         conversation_history: List[Dict[str, str]], metrics: ConversationMetrics):
        """Save conversation data to local database"""
        # Convert metrics to dict, handling enums
        metrics_dict = asdict(metrics)
        metrics_dict['stage'] = metrics.stage.value if hasattr(metrics.stage, 'value') else str(metrics.stage)
        metrics_dict['intent'] = metrics.intent.value if hasattr(metrics.intent, 'value') else str(metrics.intent)
        
        conversation_data = {
            'conversation_id': conversation_id,
            'contact': asdict(contact),
            'conversation_history': conversation_history,
            'metrics': metrics_dict,
            'last_updated': datetime.now().isoformat(),
            'created_at': self.conversations.get(conversation_id, {}).get('created_at', datetime.now().isoformat())
        }
        
        self.conversations[conversation_id] = conversation_data
        self.save_json_db(self.conversations_db, self.conversations)

    def extract_conversation_details_from_driver(self, driver) -> Dict[str, Any]:
        """Extract conversation details directly from driver - FIXED VERSION"""
        # **FIX:** Import By class
        from selenium.webdriver.common.by import By
        conversation_details = {}
        
        try:
            # Wait a bit for details to load
            time.sleep(1)
            
            # Extract participant name with MULTIPLE selectors
            name_selectors = [
                "h2.msg-entity-lockup__entity-title",
                ".msg-thread__link-to-profile",
                "a.msg-thread__link-to-profile",
                ".msg-overlay-conversation-bubble__participant-name",
                "h1.msg-entity-lockup__entity-title",
                ".msg-conversation-container__participant-names h2"
            ]
            
            for selector in name_selectors:
                try:
                    name_element = driver.find_element(By.CSS_SELECTOR, selector)
                    name_text = name_element.text.strip()
                    if name_text and len(name_text) > 0:
                        conversation_details['participant_name'] = name_text
                        logger.info(f"✅ Extracted name: {name_text}")
                        break
                except:
                    continue
            
            # If still not found, try XPath
            if 'participant_name' not in conversation_details:
                try:
                    name_element = driver.find_element(By.XPATH, "//h2[contains(@class, 'msg-entity-lockup')]")
                    name_text = name_element.text.strip()
                    if name_text:
                        conversation_details['participant_name'] = name_text
                        logger.info(f"✅ Extracted name (XPath): {name_text}")
                except:
                    logger.warning("❌ Could not extract participant name")
                    conversation_details['participant_name'] = "Unknown"
            
            # Extract headline
            headline_selectors = [
                ".msg-entity-lockup__headline",
                ".msg-thread__link-to-profile-subtitle",
                "p.msg-entity-lockup__headline"
            ]
            
            for selector in headline_selectors:
                try:
                    headline_element = driver.find_element(By.CSS_SELECTOR, selector)
                    headline_text = headline_element.text.strip()
                    if headline_text:
                        conversation_details['participant_headline'] = headline_text
                        logger.debug(f"Extracted headline: {headline_text[:50]}...")
                        break
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Error extracting conversation details: {e}")
        
        return conversation_details

    def process_inbox_enhanced(self, driver, user_name: str, max_replies: int = 20, session_id: str = None, client_instance=None) -> Dict[str, Any]:
        """
        Enhanced inbox processing with a robust, rebuilt user confirmation flow.
        """
        logger.info("🤖 Starting inbox processing with refactored user decision logic...")

        self.client = client_instance
        if not session_id:
            import uuid
            session_id = f"inbox_session_{uuid.uuid4()}"
        
        logger.info(f"📋 Inbox Session ID: {session_id}")
        
        # Initialize session state
        self.active_inbox_sessions[session_id] = {
            'status': 'running',
            'awaiting_confirmation': False,
            'current_conversation': None,
            'user_action': None,
            'stop_requested': False,
        }

        results = {
            'success': False,
            'processed': [], 
            'auto_replied': 0, 
            'skipped_by_user': 0,
            'skipped_on_timeout': 0,
            'edited_by_user': 0,
            'errors': 0,
            'total_processed': 0
        }

        try:
            logger.info(f"👤 Processing inbox for user: {user_name}")

            # Load processed conversations
            processed_conversation_ids = set()
            processed_file = "processed_conversations.json"
            try:
                if os.path.exists(processed_file):
                    with open(processed_file, 'r') as f:
                        saved_processed = json.load(f)
                        if saved_processed.get('date') == datetime.now().strftime("%Y-%m-%d"):
                            processed_conversation_ids = set(saved_processed.get('conversations', []))
                            logger.info(f"Loaded {len(processed_conversation_ids)} previously processed conversations for today.")
            except Exception as e:
                logger.debug(f"Could not load processed conversations: {e}")

            processed_count = 0
            scan_attempts = 0
            max_scans = min(max_replies * 2, 50)
            
            # Main processing loop
            while processed_count < max_replies and scan_attempts < max_scans:
                # Check for stop request
                if self.active_inbox_sessions[session_id].get('stop_requested'):
                    logger.info("🛑 Stop requested by user")
                    break
                    
                scan_attempts += 1
                logger.info(f"\n--- Inbox Scan Attempt {scan_attempts} ---")

                if not self.navigate_to_messaging_safe(driver):
                    logger.error("Failed to navigate to messaging, aborting.")
                    break
                
                time.sleep(3)
                
                try:
                    all_conversations = self.find_all_conversations(driver)
                except AttributeError:
                    logger.warning("find_all_conversations not found, using direct search")
                    # Fallback: Find conversations directly
                    time.sleep(2)
                    all_conversations = []
                    selectors = [
                        "li.msg-conversation-listitem",
                        "li.msg-conversation-card__row",
                        "li[data-view-name='conversation-list-item']",
                        "div.msg-conversation-card",
                        "li[class*='conversation-list']"
                    ]
                    for selector in selectors:
                        try:
                            items = driver.find_elements(By.CSS_SELECTOR, selector)
                            visible_items = [item for item in items if item.is_displayed()]
                            if visible_items:
                                logger.info(f"Found {len(visible_items)} conversations with: {selector}")
                                all_conversations = visible_items
                                break
                        except Exception as e:
                            logger.warning(f"Error finding conversations with {selector}: {e}")
                            continue

                if not all_conversations:
                    logger.info("No conversations found on page. Ending process.")
                    break
                
                logger.info(f"Found {len(all_conversations)} potential conversation items on page.")
                
                new_conversations_found = False
                
                for idx, conv_item in enumerate(all_conversations):
                    # Check for stop request in inner loop too
                    if self.active_inbox_sessions[session_id].get('stop_requested'):
                        break
                        
                    conv_id = self._generate_conversation_id(conv_item, idx)
                    
                    if not conv_id or conv_id in processed_conversation_ids:
                        continue

                    logger.info(f"🎯 Found NEW conversation to analyze: {conv_id[:15]}...")
                    
                    processed_conversation_ids.add(conv_id)
                    new_conversations_found = True
                    
                    try:
                        # Click and open conversation
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", conv_item)
                        time.sleep(1)
                        
                        try:
                            conv_item.click()
                        except:
                            driver.execute_script("arguments[0].click();", conv_item)
                        
                        # Wait for conversation to load
                        WebDriverWait(driver, 15).until(
                            EC.any_of(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".msg-s-message-list")),
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".msg-thread")),
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".msg-s-event-listitem"))
                            )
                        )
                        time.sleep(2)
                        
                        # Extract conversation data
                        conversation_details = self.extract_conversation_details_from_driver(driver)
                        contact = self.extract_contact_info_enhanced(driver, conversation_details)
                        conversation_history = self.get_complete_conversation_history_from_driver(driver, user_name)
                        
                        if not conversation_history:
                            logger.warning("No messages found in conversation, skipping.")
                            continue
                        
                        last_message = conversation_history[-1]
                        
                        # Skip if last message was from us
                        if last_message.get('sender', '').lower() == user_name.lower():
                            logger.info(f"⏭️ Last message was from us ({user_name}), skipping reply.")
                            continue
                        
                        results['total_processed'] += 1
                        processed_count += 1
                        
                        last_message_text = last_message.get('message', '')
                        intent = self.analyze_message_intent(last_message_text)
                        metrics = ConversationMetrics(
                            intent=intent, 
                            message_count=len(conversation_history), 
                            last_interaction=datetime.now().isoformat()
                        )
                        metrics.lead_score = self.calculate_lead_score(contact, conversation_history, metrics)
                        metrics.stage = self.determine_conversation_stage(conversation_history, intent)
                        
                        logger.info(f"📊 Processing conversation with {contact.name}: Lead score: {metrics.lead_score}, Stage: {metrics.stage.value}")
                        
                        # Save conversation data
                        self.save_conversation_data(conv_id, contact, conversation_history, metrics)
                        
                        # Check if we should auto-reply
                        if self.should_auto_reply(metrics, last_message_text):
                            # Generate AI response
                            response_message = self.generate_smart_response(contact, conversation_history, metrics)
                            logger.info(f"💬 Generated response: {response_message[:100]}...")
                            
                            # === ENHANCED REPLY PREVIEW FEATURE ===
                            # Set up awaiting confirmation state
                            self.active_inbox_sessions[session_id]['awaiting_confirmation'] = True
                            self.active_inbox_sessions[session_id]['user_action'] = None
                            current_preview = {
                                'contact': asdict(contact),
                                'conversation_history': conversation_history,
                                'generated_message': response_message,
                            }
                            
                            # Report to dashboard for preview
                            self._report_inbox_preview_to_dashboard(session_id, current_preview)
                            
                            # Wait for user decision with timeout
                            logger.info(f"⏳ Waiting for user decision for {contact.name}... (Timeout: 5 minutes)")

                            start_wait_time = time.time()
                            user_decision = None
                            
                            while time.time() - start_wait_time < 300:  # 5 minute timeout
                                if self.active_inbox_sessions[session_id].get('stop_requested'):
                                    logger.info("🛑 Stop requested by user during wait")
                                    break
                                
                                user_decision = self.active_inbox_sessions[session_id].get('user_action')
                                if user_decision:
                                    logger.info(f"👍 Received user action: {user_decision.get('action')}")
                                    break
    
                                time.sleep(2)
                            
                            self.active_inbox_sessions[session_id]['awaiting_confirmation'] = False
                            action_to_take = 'skip'  # Default to skipping on timeout
                            
                            if user_decision:
                                action_to_take = user_decision.get('action', 'skip')

                            if action_to_take in ['send', 'edit']:
                                # Prioritize the message from the user action. Fall back to the original
                                # AI response if no message was provided (i.e., a simple 'send' confirmation).
                                final_message = user_decision.get('message') or response_message
                                
                                is_edited = final_message != response_message

                                if is_edited:
                                    logger.info(f"✏️ Sending EDITED message to {contact.name} as per user confirmation.")
                                else:
                                    logger.info(f"▶️ Sending original message to {contact.name} as per user confirmation.")

                                if self.send_chat_message_enhanced(driver, final_message):
                                    if is_edited:
                                        results['edited_by_user'] += 1
                                    else:
                                        results['auto_replied'] += 1

                            elif action_to_take == 'skip':
                                if user_decision:  # Skipped by user click
                                    logger.info(f"⏭️ Skipping reply to {contact.name} based on user decision.")
                                    results['skipped_by_user'] += 1
                                else:  # Skipped on timeout
                                    logger.warning(f"⌛ Timed out waiting for user action. Skipping reply to {contact.name}.")
                                    results['skipped_on_timeout'] += 1
                        else:
                            logger.info(f"⏭️ Skipping auto-reply for {contact.name} (lead score: {metrics.lead_score})")
                            
                    except Exception as e:
                        logger.error(f"Error processing conversation {conv_id}: {e}", exc_info=True)
                        results['errors'] += 1
                        continue
                
                # Save processed conversations after each scan
                self.save_processed_conversations(processed_file, processed_conversation_ids)
                
                if not new_conversations_found:
                    logger.info("No new conversations found in this scan.")
                    if processed_count >= max_replies:
                        break
            
            # Final save
            self.save_processed_conversations(processed_file, processed_conversation_ids)
            
            results['success'] = True
            logger.info(f"✅ Inbox processing completed. Processed: {processed_count}, Auto-replied: {results['auto_replied']}")
            return results
                    
        except Exception as e:
            logger.error(f"❌ Critical error in inbox processing session {session_id}: {e}", exc_info=True)
            results['error'] = str(e)
            return results
        finally:
            # Clean up the session state
            if session_id in self.active_inbox_sessions:
                del self.active_inbox_sessions[session_id]
            logger.info(f"🧹 Cleaned up and ended inbox session {session_id}")
            
    def _generate_conversation_id(self, conv_item, idx):
        """Generate unique conversation ID"""
        from selenium.webdriver.common.by import By
        conv_id = None
        try:
            # Try multiple strategies to generate ID
            # Strategy 1: data-conversation-id attribute
            conv_id = conv_item.get_attribute('data-conversation-id')
            if conv_id:
                return conv_id

            # Strategy 2: Thread ID from URL
            try:
                links = conv_item.find_elements(By.TAG_NAME, 'a')
                for link in links:
                    href = link.get_attribute('href')
                    if href and '/messaging/thread/' in href:
                        thread_match = re.search(r'/messaging/thread/([^/?]+)', href)
                        if thread_match:
                            return f"thread_{thread_match.group(1)}"
            except:
                pass

            # Strategy 3: Hash from content
            try:
                name_text = ""
                preview_text = ""
                
                for selector in [".msg-conversation-listitem__participant-names", ".msg-conversation-card__participant-names"]:
                    try:
                        name_elem = conv_item.find_element(By.CSS_SELECTOR, selector)
                        name_text = name_elem.text.strip()
                        if name_text:
                            break
                    except:
                        continue
                
                for selector in [".msg-conversation-listitem__message-preview", ".msg-conversation-card__message-preview"]:
                    try:
                        preview_elem = conv_item.find_element(By.CSS_SELECTOR, selector)
                        preview_text = preview_elem.text.strip()
                        if preview_text:
                            break
                    except:
                        continue
                
                if name_text or preview_text:
                    content = f"{name_text}_{preview_text}"[:100]
                    return f"content_{hashlib.md5(content.encode('utf-8')).hexdigest()}"
            except:
                pass

            # Fallback
            return f"fallback_{idx}_{int(time.time())}"
            
        except:
            return f"error_{idx}_{int(time.time())}"

    
    def _report_inbox_preview_to_dashboard(self, session_id: str, preview_data: Dict[str, Any]):
        """Helper method to report the preview to the server."""
        try:
            if not self.client or not hasattr(self.client, 'config'):
                logger.warning("No client instance available for preview reporting.")
                return
            
            dashboard_url = self.client.config.get('dashboard_url')
            if not dashboard_url:
                logger.warning("Dashboard URL not configured in client.")
                return

            endpoint = f"{dashboard_url.rstrip('/')}/api/inbox_preview"
            payload = {'session_id': session_id, 'preview': preview_data}
            headers = self.client._get_auth_headers()
            
            import requests
            response = requests.post(endpoint, json=payload, headers=headers, timeout=20)
            
            if response.status_code == 200:
                logger.info(f"✅ Successfully reported inbox preview for session {session_id} to dashboard.")
            else:
                logger.warning(f"⚠️ Inbox preview report failed: {response.status_code} - {response.text[:200]}")
                
        except Exception as e:
            logger.error(f"Could not report inbox preview: {e}", exc_info=True)
    
    def handle_inbox_action(self, session_id: str, action_data: Dict[str, Any]):

        if session_id in self.active_inbox_sessions:
            logger.info(f"✅ Setting user action for session {session_id}: {action_data.get('action')}")
                # This is the crucial step that signals the waiting loop
            self.active_inbox_sessions[session_id]['user_action'] = action_data
        else:
            logger.warning(f"⚠️ Could not find active inbox session for ID: {session_id} to handle action.")
            logger.debug(f"Currently active sessions: {list(self.active_inbox_sessions.keys())}")

    def stop_inbox_session(self, session_id: str):
        """Stop an active inbox session"""
        if session_id in self.active_inbox_sessions:
            self.active_inbox_sessions[session_id]['stop_requested'] = True
            logger.info(f"🛑 Stop requested for inbox session {session_id}")
        
    def get_complete_conversation_history_from_driver(self, driver, user_name: Optional[str] = "You") -> List[Dict[str, str]]:
        """Get conversation history with multiple robust selectors for messages and senders."""
        from selenium.webdriver.common.by import By
        conversation = []
        
        try:
            participant_name = "Other"
            try:
                # Use a short wait as the name should already be loaded
                name_elem = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h2.msg-entity-lockup__entity-title, .msg-thread__link-to-profile"))
                )
                participant_name = name_elem.text.strip()
            except Exception:
                logger.debug("Could not get participant name from header, will rely on message classes.")

            message_container_selectors = [
                "li.msg-s-message-list__event",
                "div.msg-s-message-list__event",
                ".msg-s-message-group",
                ".msg-s-event-listitem"
            ]
            
            WebDriverWait(driver, 10).until(
                EC.any_of(*[EC.presence_of_element_located((By.CSS_SELECTOR, sel)) for sel in message_container_selectors])
            )
            
            message_containers = []
            for selector in message_container_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        message_containers = elements
                        logger.info(f"Found {len(message_containers)} message containers using selector: {selector}")
                        break
                except Exception:
                    continue

            if not message_containers:
                logger.warning("No message containers found with any selector.")
                return []

            for container in message_containers:
                try:
                    element_classes = container.get_attribute("class") or ""
                    
                    is_sender_me = any(me_class in element_classes for me_class in [
                        "msg-s-message-group--me", 
                        "msg-s-message-list__event--me",
                        "msg-s-event-listitem--me"
                    ])
                    sender = user_name if is_sender_me else participant_name
                    
                    message_bubble_selectors = [
                        "p.msg-s-event-listitem__body",
                        ".msg-s-message-group__body p",
                        "div.msg-s-message-list__body",
                        "p.msg-s-message-group__body"
                    ]
                    
                    content = ""
                    for selector in message_bubble_selectors:
                        try:
                            bubble = container.find_element(By.CSS_SELECTOR, selector)
                            content = bubble.text.strip()
                            if content:
                                break
                        except Exception:
                            continue
                    
                    if content:
                        conversation.append({
                            "sender": sender,
                            "message": content,
                            "timestamp": "" 
                        })
                            
                except Exception as e:
                    logger.debug(f"Error extracting a single message container: {e}")
                    continue
            
            logger.info(f"✅ Successfully extracted {len(conversation)} messages from conversation")
            return conversation
            
        except Exception as e:
            logger.error(f"❌ Critical error getting conversation history: {e}", exc_info=True)
            return []
    
    def get_conversation_at_index(self, driver, index):
        """Safely get a conversation element at a specific index"""
        try:
            conversations = self.find_all_conversations(driver)
            if index < len(conversations):
                return conversations[index]
        except Exception as e:
            logger.error(f"Could not get conversation at index {index}: {e}")
        return None
    

    def send_chat_message_enhanced(self, driver, message):
        """Send chat message with enhanced error handling"""
        from selenium.webdriver.common.by import By
        try:
            # Find message input
            input_selectors = [
                ".msg-form__contenteditable",
                "div[role='textbox'][contenteditable='true']"
            ]
            
            message_input = None
            for selector in input_selectors:
                try:
                    message_input = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if not message_input:
                return False
            
            # Type message
            message_input.click()
            time.sleep(0.5)
            message_input.clear()
            
            for char in message:
                message_input.send_keys(char)
                time.sleep(random.uniform(0.05, 0.15))
            
            # Find and click send button
            send_button = driver.find_element(By.CSS_SELECTOR, "button.msg-form__send-button[type='submit']")
            
            if send_button.is_enabled():
                send_button.click()
                time.sleep(2)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to send chat message: {e}")
            return False
        
    def debug_conversations(self, driver) -> Dict[str, Any]:
        """
        Debug helper to understand what conversations exist and why they're being filtered.
        """
        from selenium.webdriver.common.by import By
        
        logger.info("🔍 DEBUG MODE: Analyzing all conversations...")
        
        if not self.navigate_to_messaging_safe(driver):
            return {"error": "Could not navigate to messaging"}
        
        time.sleep(3)
        
        all_conversations = self.find_all_conversations(driver)
        
        debug_info = {
            "total_found": len(all_conversations),
            "conversations": []
        }
        
        for idx, conv_item in enumerate(all_conversations[:10]):  # Check first 10
            try:
                conv_debug = {
                    "index": idx,
                    "visible": conv_item.is_displayed(),
                    "classes": conv_item.get_attribute('class') or 'N/A',
                    "aria_label": conv_item.get_attribute('aria-label') or 'N/A',
                    "id": conv_item.get_attribute('id') or 'N/A',
                    "unread_indicators": {},
                    "links": []
                }
                
                # Check for unread indicators
                conv_debug["unread_indicators"]["has_unread_class"] = 'unread' in conv_debug["classes"].lower()
                conv_debug["unread_indicators"]["has_unread_in_label"] = 'unread' in conv_debug["aria_label"].lower()
                
                # Check for unread badge
                try:
                    unread_badges = conv_item.find_elements(By.CSS_SELECTOR, 
                        '.msg-conversation-card__unread-count, [data-test-id="unread-indicator"], .artdeco-entity-lockup__badge')
                    conv_debug["unread_indicators"]["unread_badge_count"] = len(unread_badges)
                except:
                    conv_debug["unread_indicators"]["unread_badge_count"] = 0
                
                # Check for bold text (often indicates unread)
                try:
                    bold_elements = conv_item.find_elements(By.CSS_SELECTOR, 'strong, b, [class*="bold"]')
                    conv_debug["unread_indicators"]["has_bold_text"] = len(bold_elements) > 0
                except:
                    conv_debug["unread_indicators"]["has_bold_text"] = False
                
                # Get all links
                try:
                    links = conv_item.find_elements(By.TAG_NAME, 'a')
                    for link in links[:3]:  # First 3 links
                        href = link.get_attribute('href')
                        if href:
                            conv_debug["links"].append(href)
                except:
                    pass
                
                # Try to get participant name
                try:
                    name_selectors = [
                        ".msg-conversation-listitem__participant-names",
                        ".msg-conversation-card__participant-names",
                        ".artdeco-entity-lockup__title"
                    ]
                    for selector in name_selectors:
                        try:
                            name_elem = conv_item.find_element(By.CSS_SELECTOR, selector)
                            conv_debug["participant_name"] = name_elem.text.strip()
                            break
                        except:
                            continue
                except:
                    conv_debug["participant_name"] = "Could not extract"
                
                # Calculate if we think it's unread
                is_unread = (
                    conv_debug["unread_indicators"]["has_unread_class"] or
                    conv_debug["unread_indicators"]["has_unread_in_label"] or
                    conv_debug["unread_indicators"]["unread_badge_count"] > 0 or
                    conv_debug["unread_indicators"]["has_bold_text"]
                )
                conv_debug["appears_unread"] = is_unread
                
                debug_info["conversations"].append(conv_debug)
                
            except Exception as e:
                logger.error(f"Error debugging conversation #{idx}: {e}")
                debug_info["conversations"].append({
                    "index": idx,
                    "error": str(e)
                })
        
        logger.info(f"📊 SUMMARY:")
        logger.info(f"  Total conversations found: {debug_info['total_found']}")
        
        unread_count = sum(1 for c in debug_info["conversations"] if c.get("appears_unread", False))
        logger.info(f"  Conversations that appear unread: {unread_count}")
        
        try:
            with open("conversation_debug.json", "w", encoding="utf-8") as f:
                json.dump(debug_info, f, indent=2, ensure_ascii=False)
            logger.info(f"  Debug info saved to: conversation_debug.json")
        except Exception as e:
            logger.warning(f"Could not save debug info: {e}")
        
        return debug_info