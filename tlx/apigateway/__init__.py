import logging
import json
from tlx.dynamodb import json_dumps
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(func):
    """ A Decorator for lambda functions. The function to be decorated by have two positional
        arguments (event, context) as any lambda handler would.  Decorating you're handler
        allows you to write idomatic python using returns and raising exception.  This handler
        catches and formats them as proxy response objects suitable for APIG.

        This function does the following:
            - prints the received `event` to the debug logs
            - Sets the generic error response
            - Ensures raised exceptions are caught and formatted correctly
            - Unforseen errors are NOT propogated back to the user
            - Forseen exceptions ARE propogated back to the user in the `response.message` field
                (Developers should raise APIGException if they want the message to return)

        The decorated function should return data that can be converted to JSON.  This can be a list, dict, string, number or boolean.
        It should raise a APIGException if the user wants to return the error message and modify the return code.  Otherwise all
        other Exceptions are returned as 500 response codes without a detailed error message.
    """
    def wrapper(*axgs):
        # Setup default response
        response = {
            "statusCode": 500,
            "body": {
                "message": "Error saving data.  Check logs for more info.",
                "response": {},
            },
        }

        def setup_error_response(msg, code=None):
            logger.error(msg)
            response["body"]["message"] = msg
            if code:
                response["statusCode"] = code

        try:  # to get successfull execution
            event, context = axgs[0], axgs[1]
            logger.info('event: {}'.format(json_dumps(event)))
            logger.debug("Received '{resource}' request with params: {queryStringParameters} and body: {body}".format(**event))

            response["statusCode"] = "200"
            response["body"]["message"] = "Success"
            response["body"]["response"] = func(event, context)

        # if not, format appropriately for proxy integration
        except APIGException as e:
            setup_error_response(f"Error: {e}", e.code)
        except json.decoder.JSONDecodeError as e:
            setup_error_response("Input data is not JSON")
        except Exception as e:  # Unforseen Exception arose
            # pass  # Returns generic error response for production deployment
            raise Exception(e)  # For local testing only
            setup_error_response(f"Error: {e}")  # For remote testing

        # Final preparation for http reponse
        if response["body"]["response"] is None:
            del response["body"]["response"]
        response["body"] = json_dumps(response["body"])
        logger.info(f"Returning repsonse: {response}")
        return response
    return wrapper


def required_fields_found(supplied, required):
    if supplied:
        return required.intersection(supplied) == required
    return False


def require_valid_inputs(supplied, required):
    if not required_fields_found(supplied, required):
        msg = f"Invalid input parameters: {list(supplied.keys())}"
        raise APIGException(msg, code=400)


def optional_fields_found(params, fields):
    if params:
        return fields.intersection(params)
    return False


class APIGException(Exception):
    """
        Differentiate these exceptions from general ones so that we can return the exception message.
        (We don't want to return general exception messages)

        e.g to return a HTTP 402 with a custom message, raise an exception like so:
        `raise APIGException('Payment required', code=402)`
    """
    def __init__(self, message, code=500):
        self.code = code
        Exception.__init__(self, message)