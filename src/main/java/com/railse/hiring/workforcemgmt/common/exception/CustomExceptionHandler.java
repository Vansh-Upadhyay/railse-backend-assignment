package com.railse.hiring.workforcemgmt.common.exception;

import com.railse.hiring.workforcemgmt.common.model.response.Response;
import com.railse.hiring.workforcemgmt.common.model.response.ResponseStatus;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;

@ControllerAdvice
public class CustomExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public final ResponseEntity<Response<Object>> handleResourceNotFoundException(ResourceNotFoundException ex) {
        ResponseStatus status = new ResponseStatus(StatusCode.NOT_FOUND.getCode(), ex.getMessage());
        Response<Object> response = new Response<>(null, null, status);
        return new ResponseEntity<>(response, HttpStatus.NOT_FOUND);
    }

    @ExceptionHandler(Exception.class)
    public final ResponseEntity<Response<Object>> handleAllExceptions(Exception ex) {
        ResponseStatus status = new ResponseStatus(StatusCode.INTERNAL_SERVER_ERROR.getCode(), "Unexpected error: " + ex.getMessage());
        Response<Object> response = new Response<>(null, null, status);
        return new ResponseEntity<>(response, HttpStatus.INTERNAL_SERVER_ERROR);
    }
}
