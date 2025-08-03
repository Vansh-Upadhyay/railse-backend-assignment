package com.railse.hiring.workforcemgmt.common.model.response;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;
import com.railse.hiring.workforcemgmt.common.exception.StatusCode;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class Response<T> {
    private T data;
    private Pagination pagination;
    private ResponseStatus status;

    public Response(T data) {
        this.data = data;
        this.pagination = null;
        this.status = new ResponseStatus(StatusCode.SUCCESS.getCode(), StatusCode.SUCCESS.getMessage());
    }

    public Response(T data, Pagination pagination, ResponseStatus status) {
        this.data = data;
        this.pagination = pagination;
        this.status = status;
    }
}
