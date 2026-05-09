import os
import tempfile


temp_dir = tempfile.mkdtemp(prefix="openwebui-anon-test-")
os.environ["WEBUI_AUTH"] = "False"
os.environ["DATA_DIR"] = temp_dir

from fastapi import Depends, FastAPI, Response
from fastapi.testclient import TestClient

from open_webui.utils.auth import get_current_user
from open_webui.utils.misc import parse_duration
from open_webui.utils.auth import create_token, decode_token


app = FastAPI()
app.state.redis = None
app.state.config = type(
    "Config",
    (),
    {
        "JWT_EXPIRES_IN": "5m",
        "USER_PERMISSIONS": {},
    },
)()


@app.get("/me")
async def me(user=Depends(get_current_user)):
    return {"email": user.email, "role": user.role}


@app.get("/session")
async def session(response: Response, user=Depends(get_current_user)):
    token = create_token(data={"id": user.id}, expires_delta=parse_duration("5m"))
    response.set_cookie("token", token, httponly=True)
    payload = decode_token(token)
    return {"email": user.email, "role": user.role, "has_token": payload is not None}


def main():
    client = TestClient(app)
    response = client.get("/me")

    assert response.status_code == 200, response.text
    assert response.json()["email"] == "guest@localhost"
    assert response.json()["role"] == "admin"
    assert "token=" in response.headers.get("set-cookie", "")

    session_response = client.get("/session")
    assert session_response.status_code == 200, session_response.text
    assert session_response.json()["email"] == "guest@localhost"
    assert session_response.json()["has_token"] is True
    assert "token=" in session_response.headers.get("set-cookie", "")


if __name__ == "__main__":
    main()
