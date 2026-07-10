from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # demo onyl - pin to Vercel url when shipping publicly
    allow_methods=["GET"],
    allow_headers=["*"],
)

NPC_DIALOGUE = {
    "guard": {
        "name": "Guard",
        "dialogue": "Welcome to Greywater. State your business, traveler.",
    },
    "miller": {
        "name": "Miller",
        "dialogue": "Mill wheel snapped last Sabbath. No flour till it's mended, and the wright's overbooked. Sorry, friend.",
    },
    "reeve": {
        "name": "Reeve",
        "dialogue": "Half the village at my door with complaints, and the crown's tax rolls due by month's end. If you've a grievance, form a queue.",
    },
}

@app.get("/health")
def health():
    return {"status": "ok", "service": "chronicle-backend"}

@app.get("/npcs/{npc_id}/dialogue")
def get_npc_dialogue(npc_id: str):
    entry = NPC_DIALOGUE.get(npc_id.lower())
    if not entry:
        raise HTTPException(status_code=404, detail=f"NPC '{npc_id}' not found")
    return {
        "npc_id": npc_id.lower(),
        "name": entry["name"],
        "dialogue": entry["dialogue"],
    }