from dataclasses import dataclass
import logging
from pathlib import Path
import re
import shlex
from enum import Enum


class Mode(Enum):
    Host = "host"
    Client = "client"


class ReqKind(Enum):
    Open = "open"
    Kill = "kill"
    HealthCheck = "hc"


class RespKind(Enum):
    Log = "log"
    Error = "error"
    Exit = "exit"
    Okay = "ok"
    SetPid = "set_pid"


@dataclass
class OpenReq:
    path: Path
    args: list[str]
    env: dict[str,str]
    kind: ReqKind = ReqKind.Open


@dataclass
class KillReq:
    pid: int
    kind: ReqKind = ReqKind.Kill


@dataclass
class LogResp:
    msg: str
    kind: RespKind = RespKind.Log


@dataclass
class ExitResp:
    exit_code: str
    kind: RespKind = RespKind.Exit


@dataclass
class ErrorResp:
    msg: str
    kind: RespKind = RespKind.Error


@dataclass
class OkayResp:
    kind: RespKind = RespKind.Okay


@dataclass
class HealthCheckReq:
    kind: ReqKind = ReqKind.HealthCheck


@dataclass
class SetPidResp:
    pid: int
    kind: RespKind = RespKind.SetPid


Req = OpenReq | KillReq | HealthCheckReq
Resp = LogResp | ExitResp | ErrorResp | OkayResp | SetPidResp


def serialize(msg: Req | Resp) -> str:
    value = msg.kind.value
    match msg:
        case OpenReq():
            args = " ".join(msg.args)
            env: list[str] = []
            for k, v in msg.env.items():
                env.append(f'{k}="{v}"')
            return f"{value} path='{msg.path}' args='{args}' env='{' '.join(env)}'"
        case KillReq():
            return f"{value} {msg.pid}"
        case SetPidResp():
            return f"{value} {msg.pid}"
        case LogResp():
            return f"{value} {msg.msg}"
        case ExitResp():
            return f"{value} {msg.exit_code}"
        case ErrorResp():
            return f"{value} {msg.msg}"
        case OkayResp():
            return f"{value}"
        case HealthCheckReq():
            return f"{value}"


path_expr = re.compile(r"path='([^']+)'")
env_expr = re.compile(r"env='([^']+)'")
args_expr = re.compile(r"args='([^']+)'")
parse_env_expr = re.compile(r"(\w+)=(\"[^\"]*\"|[^\s]+)")


def deserialize_env(input: str) -> dict[str, str]:
    env: dict[str, str] = dict()
    env_match = env_expr.search(input)
    if env_match is not None:
        (env_raw,) = env_match.groups()
        env_iter = parse_env_expr.finditer(env_raw)
        for match in env_iter:
            (key, val) = match.groups()
            env[key] = val.replace('"', "")
    return env


def deserialize(msg: str) -> Req | Resp:
    logging.debug(f"Got message {msg}")
    try:
        [kind, rest] = msg.split(" ", 1)
    except Exception:
        kind = msg.strip()
        rest = ""

    match kind:
        case ReqKind.Open.value:
            env: dict[str, str] = dict()
            args: list[str] = []
            path: str = ""

            path_match = path_expr.search(rest)
            if path_match is None:
                raise ValueError("Open expression MUST have path parameter")
            (path,) = path_match.groups()

            args_match = args_expr.search(rest)
            if args_match is not None:
                (args_raw,) = args_match.groups()
                args = shlex.split(args_raw)

            env = deserialize_env(rest)

            return OpenReq(path=Path(path), args=args, env=env)

        case ReqKind.Kill.value:
            return KillReq(int(rest))
        case RespKind.Log.value:
            return LogResp(rest)
        case RespKind.Exit.value:
            return ExitResp(rest)
        case RespKind.Error.value:
            return ErrorResp(rest)
        case RespKind.Okay.value:
            return OkayResp()
        case ReqKind.HealthCheck.value:
            return HealthCheckReq()
        case RespKind.SetPid.value:
            return SetPidResp(int(rest))

        case _:
            raise ValueError("Could not match kind for message", msg)
