package avito.innopolis.error;

import avito.innopolis.auth.exception.FieldConflictException;
import avito.innopolis.common.dto.ErrorBody;
import avito.innopolis.common.dto.ErrorEnvelope;
import avito.innopolis.common.exception.ApiException;
import jakarta.validation.ConstraintViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

@RestControllerAdvice
public class ApiErrorHandler {
    private ResponseEntity<ErrorEnvelope> build(HttpStatus status, String code, String message, Map<String,Object> details) {
        return ResponseEntity.status(status).body(new ErrorEnvelope(new ErrorBody(code,message,details,UUID.randomUUID().toString())));
    }
    @ExceptionHandler(BadCredentialsException.class)
    public ResponseEntity<ErrorEnvelope> credentials(BadCredentialsException ex) {
        return build(HttpStatus.UNAUTHORIZED,"INVALID_CREDENTIALS","Неверные учетные данные",Map.of());
    }
    @ExceptionHandler(FieldConflictException.class)
    public ResponseEntity<ErrorEnvelope> conflict(FieldConflictException ex) {
        return build(HttpStatus.CONFLICT,"FIELD_CONFLICT",ex.getMessage(),Map.of(ex.getField(),ex.getMessage()));
    }
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<ErrorEnvelope> status(ResponseStatusException ex) {
        HttpStatus code=HttpStatus.resolve(ex.getStatusCode().value());
        return build(code==null?HttpStatus.BAD_REQUEST:code,"REQUEST_FAILED",ex.getReason()==null?"Ошибка запроса":ex.getReason(),Map.of());
    }
    @ExceptionHandler(MaxUploadSizeExceededException.class)
    public ResponseEntity<ErrorEnvelope> uploadLimit(MaxUploadSizeExceededException ex) {
        return build(HttpStatus.PAYLOAD_TOO_LARGE,"FILE_TOO_LARGE","Превышен размер файла",Map.of());
    }
    @ExceptionHandler(IOException.class)
    public ResponseEntity<ErrorEnvelope> io(IOException ex) {
        return build(HttpStatus.INTERNAL_SERVER_ERROR,"FILE_ERROR","Ошибка обработки файла",Map.of());
    }
    @ExceptionHandler(ApiException.class)
    public ResponseEntity<ErrorEnvelope> api(ApiException ex) {
        return build(ex.status,ex.code,ex.getMessage(),Map.of());
    }
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorEnvelope> invalidBody(MethodArgumentNotValidException ex) {
        Map<String,Object> fields=new LinkedHashMap<>();
        ex.getBindingResult().getFieldErrors().forEach(e -> fields.put(e.getField(),e.getDefaultMessage()));
        return build(HttpStatus.BAD_REQUEST,"VALIDATION_ERROR","Ошибка валидации тела запроса",fields);
    }
    @ExceptionHandler({ConstraintViolationException.class,MethodArgumentTypeMismatchException.class,
    MissingServletRequestParameterException.class,HttpMessageNotReadableException.class,IllegalArgumentException.class
}
)
public ResponseEntity<ErrorEnvelope> invalidRequest(Exception ex) {
    return build(HttpStatus.BAD_REQUEST,"INVALID_REQUEST","Некорректные параметры или JSON",Map.of());
}
@ExceptionHandler(HandlerMethodValidationException.class)
public ResponseEntity<ErrorEnvelope> invalidMethod(HandlerMethodValidationException ex) {
    return build(HttpStatus.BAD_REQUEST,"VALIDATION_ERROR","Ошибка валидации параметров",Map.of());
}
@ExceptionHandler(NoResourceFoundException.class)
public ResponseEntity<ErrorEnvelope> noRoute(NoResourceFoundException ex) {
    return build(HttpStatus.NOT_FOUND,"ROUTE_NOT_FOUND","Маршрут не найден",Map.of());
}
@ExceptionHandler(HttpRequestMethodNotSupportedException.class)
public ResponseEntity<ErrorEnvelope> methodNotAllowed(HttpRequestMethodNotSupportedException ex) {
    return build(HttpStatus.METHOD_NOT_ALLOWED,"METHOD_NOT_ALLOWED","HTTP-метод недоступен для маршрута",Map.of());
}
@ExceptionHandler(Exception.class)
public ResponseEntity<ErrorEnvelope> unhandled(Exception ex) {
    return build(HttpStatus.INTERNAL_SERVER_ERROR,"INTERNAL_ERROR","Внутренняя ошибка сервера",Map.of());
}
}
