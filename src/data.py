from collections.abc import Mapping
from dataclasses import dataclass
import re
import shlex
from enum import Enum


class Mode(Enum):
    Host = "host"
    Client = "client"


class ReqKind(Enum):
    Open = "open"
    Kill = "kill"


class RespKind(Enum):
    Log = "log"
    Error = "error"
    Exit = "exit"
    Okay = "ok"


@dataclass
class OpenReq:
    path: str
    args: list[str]
    env: Mapping[str, str]
    kind: ReqKind = ReqKind.Open


@dataclass
class KillReq:
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


Req = OpenReq | KillReq
Resp = LogResp | ExitResp | ErrorResp | OkayResp


def serialize(msg: Req | Resp) -> str:
    match msg:
        case OpenReq():
            args = " ".join(msg.args)
            env: list[str] = []
            for key, value in msg.env.items():
                env.append(f'{key}="{value}"')
            return f"open path='{msg.path}' args='{args}' env='{' '.join(env)}'"
        case KillReq():
            return "kill"
        case LogResp():
            return f"log {msg.msg}"
        case ExitResp():
            return f"exit {msg.exit_code}"
        case ErrorResp():
            return f"error {msg.msg}"
        case OkayResp():
            return "okay"


path_expr = re.compile(r"path='([^']+)'")
env_expr = re.compile(r"env='([^']+)'")
args_expr = re.compile(r"args='([^']+)'")
parse_env_expr = re.compile(r"(\w+)=(\"[^\"]*\"|[^\s]+)")


def deserialize(msg: str) -> Req | Resp:
    [kind, rest] = msg.split(" ", 1)
    match kind:
        case ReqKind.Open.value:
            env: dict[str, str] = dict()
            args: list[str] = []
            path: str = ""

            path_match = path_expr.search(rest)
            print(path_match)
            if path_match is None:
                raise ValueError("Open expression MUST have path parameter")
            (path,) = path_match.groups()

            args_match = args_expr.search(rest)
            print(args_match)
            if args_match is not None:
                (args_raw,) = args_match.groups()
                args = shlex.split(args_raw)

            env_match = env_expr.search(rest)
            print(env_match)
            if env_match is not None:
                (env_raw,) = env_match.groups()
                env_iter = parse_env_expr.finditer(env_raw)
                for match in env_iter:
                    (key, val) = match.groups()
                    env[key] = val.replace('"', "")

            return OpenReq(path=path, args=args, env=env)

        case ReqKind.Kill.value:
            return KillReq()
        case RespKind.Log.value:
            return LogResp(msg=rest)
        case RespKind.Exit.value:
            return ExitResp(exit_code=rest)
        case RespKind.Error.value:
            return ErrorResp(msg=rest)
        case RespKind.Okay.value:
            return OkayResp()

        case _:
            raise ValueError("Could not match kind for message", msg)
