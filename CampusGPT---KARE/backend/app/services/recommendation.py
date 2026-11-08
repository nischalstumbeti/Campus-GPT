"""Recommendation engine for courses/colleges based on user profile. Uses Gemini only."""
import asyncio
from app.config import get_settings
from app.services.demo_responses import DEMO_RECOMMENDATIONS

settings = get_settings()


async def get_recommendations(
    course: str = None,
    subject: str = None,
    budget: str = None,
    marks: float = None,
    board: str = None,
    state: str = None,
    program_level: str = None,
) -> dict:
    """Generate personalized course/college recommendations. Uses demo when no API key."""
    inputs = {
        "course": course,
        "subject": subject,
        "budget": budget,
        "marks": marks,
        "board": board,
        "state": state,
        "program_level": program_level,
    }
    if not settings.GEMINI_API_KEY:
        return {"recommendations": DEMO_RECOMMENDATIONS, "inputs": inputs}

    import google.generativeai as genai
    genai.configure(api_key=settings.GEMINI_API_KEY)
    prompt = f"""You are a career counselor for KARE (Kalasalingam Academy of Research and Education).

Student profile:
- Program level: {program_level or 'Not specified'}
- Course interest: {course or 'Not specified'}
- Subject / stream: {subject or 'Not specified'}
- Marks obtained (%): {marks or 'Not specified'}
- Board: {board or 'Not specified'}
- State: {state or 'Not specified'}
- Budget: {budget or 'Not specified'}

Provide 3-5 personalized recommendations:
1. Courses/programs that suit their profile
2. Brief "Why this recommendation" for each
3. Prerequisites or next steps if relevant

Base recommendations on KARE offerings: Bachelor of Technology, Master of Technology, Bachelor of Science, Master of Science, Bachelor of Arts, Master of Arts, MBA, BBA, Bachelor of Commerce, Master of Commerce, Doctor of Philosophy.
Placement: avg ~8.5 LPA, highest ~44 LPA. NAAC A++, NIRF ranked.
Format as clear, professional advice. Do not guarantee admission."""

    try:
        model = genai.GenerativeModel(settings.GEMINI_CHAT_MODEL)
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config={"temperature": 0.5, "max_output_tokens": 600},
        )
        answer = response.text if response and hasattr(response, "text") else DEMO_RECOMMENDATIONS
    except Exception:
        answer = DEMO_RECOMMENDATIONS

    return {"recommendations": answer, "inputs": inputs}
