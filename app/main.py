from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from fastapi.responses import RedirectResponse
from app.db import engine, Base, get_db
from app.routers import watchlist, demo
from app.routers.watchlist import get_ranked_watchlist, mark_watchlist_seen

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Market Watchlist")
templates = Jinja2Templates(directory="app/templates")
app.include_router(watchlist.router)
app.include_router(demo.router)


@app.get("/watchlist/{user_id}", response_class=HTMLResponse)
def view_watchlist(request: Request, user_id: int, error: str = None, db: Session = Depends(get_db)):
    ranked = get_ranked_watchlist(user_id, db)
    mark_watchlist_seen(user_id, ranked, db)
    return templates.TemplateResponse(
        "watchlist.html", {"request": request, "user_id": user_id, "stocks": ranked, "error": error}
    )


@app.get("/")
def root():

    return RedirectResponse(url="/watchlist/1")